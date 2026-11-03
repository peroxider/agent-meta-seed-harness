"""SH-SESS-02: per-point process loss recovery from committed State only.

Each scenario kills the owned daemon at one protocol boundary and restarts a
fresh coordinator. Recovery replays the exact journaled command bytes, never
guesses a Task identity, and never duplicates model calls or transcript
appends. Probe events from the overridden offline Provider count real model
dispatches across daemon generations.
"""

import asyncio
import json
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json

from agent_meta_seed_harness.session_coordinator import (
    PERMISSIONS,
    SUBMIT_METHOD,
    WRITEBACK_METHOD,
    open_session,
    reattach,
)

from recovery_runtime import probe_events
from seed_actor import create_actor
from seed_package import activate_seed, install_seed, seed_bundle, wait_ready
from seed_runtime import daemon_process

SUBMIT_1 = "task://019a44d0-0000-7000-8000-000000000001"
WRITEBACK_1 = "task://019a44d0-0000-7000-8000-000000000002"
SESSION_DOCUMENT = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures/session/empty-v1.json").read_bytes()
)

PROVIDER = b'''
import asyncio
import json

from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import JsonPart, ModelResponse, ProviderUsage, TextPart, ToolCallPart
from agent_meta_runtime.sdk.packages import canonical_json


async def invoke_fake(request):
    print(canonical_json({"seed_probe_call": "model", "ordinal": request.ordinal}).decode(), flush=True)
    value = json.loads(rendered_sections(request.projection)["task_input"])
    if not isinstance(value, dict) or set(value) - {"provider", "scenario", "value"} or value.get("provider") != "fake":
        raise ValueError("explicit fake Provider selection required")
    scenario = value.get("scenario", "terminal")
    payload = value.get("value", "hello")
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > 4096:
        raise ValueError("bounded text value required")
    if scenario == "wait":
        await asyncio.Event().wait()
    if scenario == "unknown_tool":
        return ModelResponse(
            (ToolCallPart("missing-1", "seed.missing", canonical_json({"value": payload}).decode()),),
            "TOOL_CALL", ProviderUsage(None, None, 0))
    return ModelResponse(
        (TextPart(payload), JsonPart({"provider": "fake"}), TextPart("done")),
        "STOP", ProviderUsage(None, None, 0))
'''


def instrumented_bundle(**options):
    options.setdefault("overrides", {"agent_meta_seed_harness/providers/fake.py": PROVIDER})
    return seed_bundle(**options)


def kill(process):
    process.kill()
    process.wait(timeout=10)


def model_events(owner):
    return [event["seed_probe_call"] for event in probe_events(owner)]


def test_pending_before_submit_recovers_without_new_task(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="pending") as first:
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

        session = asyncio.run(reserve_only())
        assert model_events(first) == []
        kill(first.process)
    with daemon_process(tmp_path, publishers=[publisher], label="after-pending") as second:
        asyncio.run(wait_ready(second.data_dir))

        async def recover(previous):
            client = await connect(second.data_dir, authority=authority)
            try:
                session = await reattach(client, authority, previous)
                document = await session.observe_transcript()
                assert document["pending"]["message_id"] == "message-1"
                assert document["pending"]["task_id"] is None
                assert (await session.observe_journal())["entries"] == []
                await session.submit_pending(SUBMIT_1)
                await session.complete_pending(WRITEBACK_1)
                committed = await session.observe_transcript()
                assert [item["message_id"] for item in committed["messages"]] == ["message-1"]
                assert committed["pending"] is None
                assert session.submitted == [SUBMIT_1]
            finally:
                await client.aclose()

        asyncio.run(recover(session))
        assert model_events(second) == ["model"]


def test_ambiguous_journal_write_recovers_registered_bytes(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="journal") as first:
        install_seed(first.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(first.data_dir))
        authority = create_actor(first.data_dir, permissions=PERMISSIONS)

        async def journal_then_die():
            client = await connect(first.data_dir, authority=authority)
            try:
                session = await open_session(client, authority, SESSION_DOCUMENT)
                await session.reserve("message-1", "canary")
                await session.journal_submit(SUBMIT_1)
                return session
            finally:
                await client.aclose()

        session = asyncio.run(journal_then_die())
        kill(first.process)
    with daemon_process(tmp_path, publishers=[publisher], label="after-journal") as second:
        asyncio.run(wait_ready(second.data_dir))

        async def recover(previous):
            client = await connect(second.data_dir, authority=authority)
            try:
                session = await reattach(client, authority, previous)
                assert (await session.observe_transcript())["pending"]["task_id"] is None
                journal = await session.observe_journal()
                assert [entry["stage"] for entry in journal["entries"]] == ["SUBMIT"]
                # The journaled bytes are replayed exactly; no envelope is
                # regenerated and no second Task is created.
                envelope = await session.recover_pending_dispatch("message-1")
                receipt = await client.execute_command(SUBMIT_METHOD, envelope)
                task_id = receipt.resource["task_id"]
                assert len(session.submitted) == 0
                session.submitted.append(SUBMIT_1)
                await session.record_receipt(task_id, SUBMIT_1)
                await session.complete_pending(WRITEBACK_1)
                committed = await session.observe_transcript()
                assert committed["messages"][0]["task_id"] == task_id
                execution = await client.get_task_execution(task_id)
                assert execution["consumed_budget"]["model_calls"] == 1
            finally:
                await client.aclose()

        asyncio.run(recover(session))
        assert model_events(second) == ["model"]


def test_lost_submit_receipt_replays_original_command(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="receipt") as first:
        install_seed(first.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(first.data_dir))
        authority = create_actor(first.data_dir, permissions=PERMISSIONS)

        async def submit_and_lose_receipt():
            client = await connect(first.data_dir, authority=authority)
            try:
                session = await open_session(client, authority, SESSION_DOCUMENT)
                await session.reserve("message-1", "canary")
                envelope = await session.journal_submit(SUBMIT_1)
                receipt = await client.execute_command(SUBMIT_METHOD, envelope)
                task_id = receipt.resource["task_id"]
                result, terminal = await client.wait_task(task_id, timeout_s=15)
                assert terminal and result["status"] == "SUCCEEDED", result
                return session, envelope, task_id
            finally:
                await client.aclose()

        session, envelope, task_id = asyncio.run(submit_and_lose_receipt())
        assert model_events(first) == ["model"]
        kill(first.process)
    with daemon_process(tmp_path, publishers=[publisher], label="after-receipt") as second:
        asyncio.run(wait_ready(second.data_dir))

        async def recover(previous):
            client = await connect(second.data_dir, authority=authority)
            try:
                session = await reattach(client, authority, previous)
                assert (await session.observe_transcript())["pending"]["task_id"] is None
                journal = await session.observe_journal()
                assert [entry["stage"] for entry in journal["entries"]] == ["SUBMIT"]
                replay = await client.execute_command(SUBMIT_METHOD, envelope)
                assert replay.resource["task_id"] == task_id
                await session.record_receipt(task_id, SUBMIT_1)
                await session.complete_pending(WRITEBACK_1)
                committed = await session.observe_transcript()
                assert committed["messages"][0]["task_id"] == task_id
                assert committed["messages"][0]["terminal_status"] == "SUCCEEDED"
                execution = await client.get_task_execution(task_id)
                assert execution["consumed_budget"]["model_calls"] == 1
            finally:
                await client.aclose()

        asyncio.run(recover(session))
        # The committed terminal is re-observed; the model is never re-called.
        assert model_events(second) == []


def test_terminal_before_writeback_recovers_without_redispatch(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="terminal") as first:
        install_seed(first.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(first.data_dir))
        authority = create_actor(first.data_dir, permissions=PERMISSIONS)

        async def observe_terminal():
            client = await connect(first.data_dir, authority=authority)
            try:
                session = await open_session(client, authority, SESSION_DOCUMENT)
                await session.reserve("message-1", "canary")
                task_id = await session.submit_pending(SUBMIT_1)
                result, terminal = await client.wait_task(task_id, timeout_s=15)
                assert terminal and result["status"] == "SUCCEEDED", result
                return session, task_id
            finally:
                await client.aclose()

        session, task_id = asyncio.run(observe_terminal())
        assert model_events(first) == ["model"]
        kill(first.process)
    with daemon_process(tmp_path, publishers=[publisher], label="after-terminal") as second:
        asyncio.run(wait_ready(second.data_dir))

        async def recover(previous):
            client = await connect(second.data_dir, authority=authority)
            try:
                session = await reattach(client, authority, previous)
                document = await session.observe_transcript()
                assert document["pending"]["task_id"] == task_id
                assert [entry["stage"] for entry in
                        (await session.observe_journal())["entries"]] == ["SUBMIT"]
                await session.complete_pending(WRITEBACK_1)
                committed = await session.observe_transcript()
                assert [item["message_id"] for item in committed["messages"]] == ["message-1"]
                assert committed["pending"] is None
                # The fresh incarnation submitted nothing new.
                assert session.submitted == []
            finally:
                await client.aclose()

        asyncio.run(recover(session))
        assert model_events(second) == []


def test_writeback_response_loss_confirms_exactly_one_append(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="writeback") as first:
        install_seed(first.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(first.data_dir))
        authority = create_actor(first.data_dir, permissions=PERMISSIONS)

        async def commit_writeback():
            client = await connect(first.data_dir, authority=authority)
            try:
                session = await open_session(client, authority, SESSION_DOCUMENT)
                await session.reserve("message-1", "canary")
                await session.submit_pending(SUBMIT_1)
                result, terminal = await client.wait_task(
                    session.document["pending"]["task_id"], timeout_s=15
                )
                assert terminal and result["status"] == "SUCCEEDED", result
                envelope, committed = await session.register_writeback(WRITEBACK_1, result)
                await client.execute_command(WRITEBACK_METHOD, envelope)
                return session, envelope, committed
            finally:
                await client.aclose()

        session, envelope, committed = asyncio.run(commit_writeback())
        assert model_events(first) == ["model"]
        kill(first.process)
    with daemon_process(tmp_path, publishers=[publisher], label="after-writeback") as second:
        asyncio.run(wait_ready(second.data_dir))

        async def recover(previous):
            client = await connect(second.data_dir, authority=authority)
            try:
                session = await reattach(client, authority, previous)
                current = await session.observe_transcript()
                assert current == committed
                assert [item["message_id"] for item in current["messages"]] == ["message-1"]
                replay = await client.execute_command(WRITEBACK_METHOD, envelope)
                assert replay.resource["cas_revision"] == session.revision[1]
                assert (await session.observe_transcript()) == committed
                journal = await session.observe_journal()
                assert [entry["stage"] for entry in journal["entries"]] == [
                    "SUBMIT", "WRITEBACK",
                ]
            finally:
                await client.aclose()

        asyncio.run(recover(session))
        assert model_events(second) == []


def test_failed_and_cancelled_terminals_are_recorded_without_redispatch(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="outcomes") as first:
        install_seed(first.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(first.data_dir))
        authority = create_actor(first.data_dir, permissions=PERMISSIONS)

        async def run():
            client = await connect(first.data_dir, authority=authority)
            try:
                session = await open_session(client, authority, SESSION_DOCUMENT)
                # A declared failed terminal is committed to the transcript.
                await session.reserve("message-1", "canary", scenario="unknown_tool")
                task_id = await session.submit_pending(SUBMIT_1)
                await session.complete_pending(WRITEBACK_1)
                committed = await session.observe_transcript()
                assert committed["messages"][0]["terminal_status"] == "FAILED"
                assert committed["messages"][0]["result_artifact_id"] is None
                assert committed["messages"][0]["task_id"] == task_id
                assert session.submitted == [SUBMIT_1]
                # A cancelled Task is a terminal too; it is never resubmitted.
                await session.reserve("message-2", "canary", scenario="wait")
                task_id = await session.submit_pending(
                    "task://019a44d0-0000-7000-8000-000000000003"
                )
                await client.cancel_task(
                    realm_id="realm://main", actor_id=authority.actor_id, task_id=task_id
                )
                await session.complete_pending(
                    "task://019a44d0-0000-7000-8000-000000000004"
                )
                committed = await session.observe_transcript()
                assert [item["terminal_status"] for item in committed["messages"]] == [
                    "FAILED", "CANCELLED",
                ]
                assert session.submitted == [
                    SUBMIT_1, "task://019a44d0-0000-7000-8000-000000000003",
                ]
            finally:
                await client.aclose()

        asyncio.run(run())


def test_seed_upgrade_preserves_committed_session_and_continues(tmp_path):
    first_bundle, publisher = instrumented_bundle()
    second_bundle, _ = instrumented_bundle(version="0.1.1-dev.1", descriptor_revision=2)
    with daemon_process(tmp_path, publishers=[publisher], label="upgrade") as owner:
        install_seed(owner.data_dir, tmp_path, first_bundle)
        asyncio.run(wait_ready(owner.data_dir))
        authority = create_actor(owner.data_dir, permissions=PERMISSIONS)

        async def run():
            client = await connect(owner.data_dir, authority=authority)
            try:
                session = await open_session(client, authority, SESSION_DOCUMENT)
                await session.reserve("message-1", "before upgrade")
                task_id = await session.submit_pending(SUBMIT_1)
                before = await client.get_task_trace(task_id)
                await session.complete_pending(WRITEBACK_1)
                # Cutover to a new Seed version; owner-owned session States
                # are untouched by package activation.
                new_id = install_seed(owner.data_dir, tmp_path, second_bundle, activate=False)
                upgraded = activate_seed(owner.data_dir, second_bundle, new_id)
                await wait_ready(owner.data_dir)
                await session.reserve("message-2", "after upgrade")
                task_id = await session.submit_pending(
                    "task://019a44d0-0000-7000-8000-000000000003"
                )
                after = await client.get_task_trace(task_id)
                await session.complete_pending(
                    "task://019a44d0-0000-7000-8000-000000000004"
                )
                committed = await session.observe_transcript()
                assert [item["message_id"] for item in committed["messages"]] == [
                    "message-1", "message-2",
                ]
                assert committed["pending"] is None
                journal = await session.observe_journal()
                assert [entry["stage"] for entry in journal["entries"]] == [
                    "SUBMIT", "WRITEBACK", "SUBMIT", "WRITEBACK",
                ]
                # Each round froze its own serving composition; the second ran
                # under the upgraded cutover, not the stale pointer.
                assert before["actions"][0]["composition_id"] != after["actions"][0]["composition_id"]
                assert after["actions"][0]["composition_id"] == upgraded["composition_id"]
            finally:
                await client.aclose()

        asyncio.run(run())
        assert len(model_events(owner)) == 2
