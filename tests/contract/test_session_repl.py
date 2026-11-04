"""S06 plan steps 4/5: minimal interactive front-end and round diagnostics.

The REPL drives complete durable rounds over the coordinator's signed public
commands, recovers a pending round on attach before new admission, and
explains any round's lineage from transcript, journal and public Task traces.
"""

import asyncio
import json
import time
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json

from agent_meta_seed_harness.repl import (
    SessionRepl,
    explain_round,
    next_message_id,
    render_explanation,
)
from agent_meta_seed_harness.session import SessionConflict
from agent_meta_seed_harness.session_coordinator import (
    PERMISSIONS,
    open_session,
    reattach,
)

from recovery_runtime import probe_events
from seed_actor import create_actor
from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import daemon_process

SESSION_DOCUMENT = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures/session/empty-v1.json").read_bytes()
)

PROVIDER = b'''
import asyncio
import json

from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import JsonPart, ModelResponse, ProviderUsage, TextPart
from agent_meta_runtime.sdk.packages import canonical_json


async def invoke_fake(request):
    print(canonical_json({"seed_probe_call": "model", "ordinal": request.ordinal}).decode(), flush=True)
    value = json.loads(rendered_sections(request.projection)["task_input"])
    if not isinstance(value, dict) or set(value) - {"provider", "scenario", "value"} or value.get("provider") != "fake":
        raise ValueError("explicit fake Provider selection required")
    payload = value.get("value", "hello")
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > 4096:
        raise ValueError("bounded text value required")
    return ModelResponse(
        (TextPart(payload), JsonPart({"provider": "fake"}), TextPart("done")),
        "STOP", ProviderUsage(None, None, 0))
'''


def instrumented_bundle(**options):
    options.setdefault("overrides", {"agent_meta_seed_harness/providers/fake.py": PROVIDER})
    return seed_bundle(**options)


def model_events(owner):
    return [event["seed_probe_call"] for event in probe_events(owner)]


def wait_model_events(owner, count):
    """The daemon writes probe lines to a redirected file; allow it to land."""
    deadline = time.monotonic() + 10
    events = model_events(owner)
    while len(events) < count and time.monotonic() < deadline:
        time.sleep(0.05)
        events = model_events(owner)
    return events


def test_next_message_id_is_stable_and_collision_free():
    document = json.loads(json.dumps(SESSION_DOCUMENT))
    assert next_message_id(document) == "message-1"
    # The same observed state always proposes the same identity.
    assert next_message_id(document) == "message-1"
    document["messages"].append({
        "message_id": "message-1", "input_artifact_id": "artifact://sha256/" + "0" * 64,
        "task_id": "task://019a44d0-0000-7000-8000-000000000001",
        "terminal_status": "SUCCEEDED", "result_artifact_id": "artifact://sha256/" + "1" * 64,
    })
    document["pending"] = {
        "message_id": "message-3", "input_artifact_id": "artifact://sha256/" + "2" * 64,
        "task_id": None, "submit_command_id": None, "writeback_command_id": None,
        "journal_state_id": document["config"]["journal_state_id"],
    }
    assert next_message_id(document) == "message-2"


def test_explain_round_rejects_unknown_messages_and_malformed_traces():
    document = json.loads(json.dumps(SESSION_DOCUMENT))
    journal = {"schema": "seed/session-command-journal/v1",
               "session_id": document["session_id"], "entries": []}
    with pytest.raises(SessionConflict, match="no committed or pending round"):
        explain_round(document, journal, message_id="message-1")
    document["messages"].append({
        "message_id": "message-1", "input_artifact_id": "artifact://sha256/" + "0" * 64,
        "task_id": "task://019a44d0-0000-7000-8000-000000000001",
        "terminal_status": "SUCCEEDED", "result_artifact_id": "artifact://sha256/" + "1" * 64,
    })
    explanation = explain_round(document, journal, message_id="message-1")
    assert explanation["state"] == "committed" and explanation["journal"] == []
    with pytest.raises(ValueError, match="malformed public Task trace"):
        explain_round(document, journal, message_id="message-1", trace={"actions": []})
    with pytest.raises(ValueError, match="malformed public Task trace"):
        explain_round(document, journal, message_id="message-1", trace="task-trace")
    verified = explain_round(
        document, journal, message_id="message-1",
        trace={"actions": [{"composition_id": "composition://" + "a" * 64}]},
    )
    assert verified["composition_id"] == "composition://" + "a" * 64
    assert verified["actions"] == 1


@pytest.fixture
def session_environment(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher]) as owner:
        install_seed(owner.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(owner.data_dir))
        authority = create_actor(owner.data_dir, permissions=PERMISSIONS)
        yield owner, authority


async def scripted_run(repl, lines, outputs):
    iterator = iter(lines)

    async def reader():
        try:
            return next(iterator)
        except StopIteration:
            return None

    await repl.run(reader, outputs.append)
    return outputs


def test_repl_drives_rounds_history_and_explains_lineage(session_environment):
    owner, authority = session_environment

    async def scenario():
        client = await connect(owner.data_dir, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            repl = SessionRepl(session)
            assert await repl.attach() is None
            # One free-text line is one durable round with a stable identity.
            assert await repl.handle_line("first") == ["committed message-1"]
            assert await repl.handle_line("second") == ["committed message-2"]
            committed = await session.observe_transcript()
            assert [item["message_id"] for item in committed["messages"]] == [
                "message-1", "message-2",
            ]
            assert committed["pending"] is None
            assert len(session.submitted) == 2
            for item in committed["messages"]:
                execution = await client.get_task_execution(item["task_id"])
                assert execution["consumed_budget"]["model_calls"] == 1
            # Round lineage explains exactly one round through public records.
            explanation = await repl.explain("message-1")
            assert explanation["state"] == "committed"
            assert explanation["task_id"] == committed["messages"][0]["task_id"]
            assert explanation["terminal_status"] == "SUCCEEDED"
            assert [entry["stage"] for entry in explanation["journal"]] == [
                "SUBMIT", "WRITEBACK",
            ]
            for entry in explanation["journal"]:
                assert len(entry["command_sha256"]) == 64
            trace = await client.get_task_trace(explanation["task_id"])
            assert explanation["composition_id"] == trace["actions"][0]["composition_id"]
            # The rendered lineage is bounded and reflects the same records.
            rendered = render_explanation(explanation)
            assert any("terminal=SUCCEEDED" in line for line in rendered)
            assert any("composition=" in line for line in rendered)
            assert await repl.handle_line("/explain message-1") == rendered
            history = await repl.handle_line("/history")
            assert history == [
                "message-1 SUCCEEDED task=" + committed["messages"][0]["task_id"],
                "message-2 SUCCEEDED task=" + committed["messages"][1]["task_id"],
            ]
            # A full scripted interactive session reaches the same records.
            fresh = SessionRepl(session)
            outputs = await scripted_run(
                fresh, ["/explain message-2", "/quit"], []
            )
            assert any("message-2 [committed]" in line for line in outputs)
            assert outputs[-1] == "session closed; committed State is durable"
            assert fresh.stopped
            with pytest.raises(SessionConflict):
                await repl.explain("message-9")
            # Blank lines and unknown commands never touch durable state.
            assert await repl.handle_line("") == []
            revision = session.revision
            assert "commands:" in (await repl.handle_line("/bogus"))[0]
            await session.observe_transcript()
            assert session.revision == revision
        finally:
            await client.aclose()

    asyncio.run(scenario())
    assert len(model_events(owner)) == 2


def test_repl_attaches_and_recovers_pending_before_new_input(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="reserve") as first:
        install_seed(first.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(first.data_dir))
        authority = create_actor(first.data_dir, permissions=PERMISSIONS)

        async def reserve_only():
            client = await connect(first.data_dir, authority=authority)
            try:
                session = await open_session(client, authority, SESSION_DOCUMENT)
                await session.reserve("message-1", "canary")
                return session
            finally:
                await client.aclose()

        previous = asyncio.run(reserve_only())
        assert model_events(first) == []
        first.process.kill()
        first.process.wait(timeout=10)
    with daemon_process(tmp_path, publishers=[publisher], label="after-reserve") as second:
        asyncio.run(wait_ready(second.data_dir))

        async def recover_and_continue(previous):
            client = await connect(second.data_dir, authority=authority)
            try:
                session = await reattach(client, authority, previous)
                repl = SessionRepl(session)
                # Attach finishes the interrupted round before new admission;
                # no journal entry existed, so a new durable identity is used.
                recovered = await repl.attach()
                assert [item["message_id"] for item in recovered["messages"]] == [
                    "message-1",
                ]
                assert recovered["pending"] is None
                assert await repl.handle_line("after") == ["committed message-2"]
                committed = await session.observe_transcript()
                assert [item["message_id"] for item in committed["messages"]] == [
                    "message-1", "message-2",
                ]
                journal = await session.observe_journal()
                assert [entry["stage"] for entry in journal["entries"]] == [
                    "SUBMIT", "WRITEBACK", "SUBMIT", "WRITEBACK",
                ]
                # One model call per round, across the restart boundary.
                for item in committed["messages"]:
                    execution = await client.get_task_execution(item["task_id"])
                    assert execution["consumed_budget"]["model_calls"] == 1
                explanation = await repl.explain("message-1")
                assert explanation["state"] == "committed"
                assert len(explanation["journal"]) == 2
                return session
            finally:
                await client.aclose()

        asyncio.run(recover_and_continue(previous))
        assert model_events(second) == ["model", "model"]


def test_repl_explains_a_pending_round_before_completing_it(session_environment):
    owner, authority = session_environment

    async def scenario():
        client = await connect(owner.data_dir, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            repl = SessionRepl(session)
            assert await repl.attach() is None
            # A dispatched round without its observed terminal is pending;
            # its reserved submit identity stays explainable from records.
            await session.reserve("message-1", "canary")
            task_id = await session.submit_pending()
            submit_id = session.submitted[0]
            assert await repl.handle_line("/history") == ["message-1 PENDING"]
            explanation = await repl.explain("message-1")
            assert explanation["state"] == "pending"
            assert explanation["task_id"] == task_id
            assert explanation["submit_command_id"] == submit_id
            assert explanation["writeback_command_id"] is None
            assert [entry["stage"] for entry in explanation["journal"]] == ["SUBMIT"]
            assert explanation["journal"][0]["command_id"] == submit_id
            assert len(explanation["journal"][0]["command_sha256"]) == 64
            rendered = render_explanation(explanation)
            assert rendered[0] == (
                "message-1 [pending] task=" + task_id
                + " input=" + explanation["input_artifact_id"]
            )
            assert any(
                f"submit={submit_id} writeback=None" in line for line in rendered
            )
            assert await repl.handle_line("/explain message-1") == rendered
            # Completing the externally driven round moves the same identity
            # into the committed branch of the same lineage query.
            await session.complete_pending()
            committed = await repl.explain("message-1")
            assert committed["state"] == "committed"
            assert committed["task_id"] == task_id
            assert committed["terminal_status"] == "SUCCEEDED"
            assert [entry["stage"] for entry in committed["journal"]] == [
                "SUBMIT", "WRITEBACK",
            ]
            # New admission works once the pending round is complete.
            assert await repl.handle_line("second") == ["committed message-2"]
            history = await repl.handle_line("/history")
            assert history[0] == "message-1 SUCCEEDED task=" + task_id
            assert history[1].startswith("message-2 SUCCEEDED task=")
        finally:
            await client.aclose()

    asyncio.run(scenario())
    assert wait_model_events(owner, 2) == ["model", "model"]


def test_repl_commits_a_failed_round_and_records_its_terminal(session_environment):
    owner, authority = session_environment

    async def scenario():
        client = await connect(owner.data_dir, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            repl = SessionRepl(session)
            assert await repl.attach() is None
            # The over-bound value is refused at Task admission; the round is
            # still durably committed with its FAILED terminal, not retried.
            assert await repl.handle_line("x" * 4097) == ["committed message-1"]
            committed = await session.observe_transcript()
            assert committed["pending"] is None
            assert committed["messages"][0]["terminal_status"] == "FAILED"
            assert committed["messages"][0]["result_artifact_id"] is None
            execution = await client.get_task_execution(
                committed["messages"][0]["task_id"]
            )
            assert execution["invocations"] == []
            assert execution["error"] == "INVALID_ARGUMENT"
            explanation = await repl.explain("message-1")
            assert explanation["state"] == "committed"
            assert explanation["terminal_status"] == "FAILED"
            assert explanation["result_artifact_id"] is None
            assert "composition_id" in explanation
            rendered = await repl.handle_line("/explain message-1")
            assert any("terminal=FAILED" in line for line in rendered)
            assert (await repl.handle_line("/history"))[0].startswith(
                "message-1 FAILED task="
            )
            # The same session stays usable for a healthy round afterwards.
            assert await repl.handle_line("fine") == ["committed message-2"]
            final = await session.observe_transcript()
            assert [item["terminal_status"] for item in final["messages"]] == [
                "FAILED", "SUCCEEDED",
            ]
        finally:
            await client.aclose()

    asyncio.run(scenario())
    # Only the healthy round reaches the Provider; the admission-refused one
    # never invoked the model.
    assert wait_model_events(owner, 1) == ["model"]
