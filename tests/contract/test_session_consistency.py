"""SH-SESS-01: session consistency through the public coordination protocol.

One message is one Task; transcript/journal are separate protected States;
dedup, conflicts, journal registration and projections follow the S06 plan.
"""

import asyncio
import copy
import json
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import StableError, connect
from agent_meta_runtime.sdk.context import SECTION_DELIMITER
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

from agent_meta_seed_harness.session import SessionConflict, validate_session
from agent_meta_seed_harness.session_coordinator import (
    PERMISSIONS,
    WRITEBACK_METHOD,
    message_input,
    open_session,
)

from contract.test_public_state_management import REALM, upload

from seed_actor import create_actor
from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import daemon_process

SESSION = "session://019a44d0-0000-7000-8000-000000000001"
SUBMIT_1 = "task://019a44d0-0000-7000-8000-000000000001"
WRITEBACK_1 = "task://019a44d0-0000-7000-8000-000000000002"
SUBMIT_2 = "task://019a44d0-0000-7000-8000-000000000003"
WRITEBACK_2 = "task://019a44d0-0000-7000-8000-000000000004"
SESSION_DOCUMENT = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures/session/empty-v1.json").read_bytes()
)


@pytest.fixture
def session_environment(tmp_path):
    bundle, publisher = seed_bundle()
    with daemon_process(tmp_path, publishers=[publisher]) as owner:
        install_seed(owner.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(owner.data_dir))
        authority = create_actor(owner.data_dir, permissions=PERMISSIONS)
        yield owner.data_dir, authority


def committed_ids(message):
    return {
        key: message[key]
        for key in ("message_id", "input_artifact_id", "task_id", "result_artifact_id")
    }


def test_message_retry_conflict_and_concurrency_preserve_one_task_per_message(
    session_environment,
):
    data, authority = session_environment

    async def scenario():
        client = await connect(data, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            await session.reserve("message-1", "first")
            await session.submit_pending(SUBMIT_1)
            await session.complete_pending(WRITEBACK_1)
            assert session.submitted == [SUBMIT_1]
            observed = await session.observe_transcript()
            assert observed["pending"] is None
            # An identical retry recovers the committed operation; the
            # content-addressed input resolves to the same artifact.
            retried = await session.reserve("message-1", "first")
            assert retried == observed
            assert session.submitted == [SUBMIT_1]
            with pytest.raises(SessionConflict, match="different input"):
                await session.reserve("message-1", "changed")
            assert session.submitted == [SUBMIT_1]
            current = await session.observe_transcript()
            assert current == observed
            # Concurrent admission is refused while one message is pending.
            await session.reserve("message-2", "second")
            with pytest.raises(SessionConflict, match="already pending"):
                await session.reserve("message-3", "third")
            assert session.submitted == [SUBMIT_1]
            pending = await session.observe_transcript()
            assert pending["pending"]["message_id"] == "message-2"
            assert pending["messages"] == observed["messages"]
            await session.submit_pending(SUBMIT_2)
            await session.complete_pending(WRITEBACK_2)
            committed = await session.observe_transcript()
            assert [item["message_id"] for item in committed["messages"]] == [
                "message-1",
                "message-2",
            ]
            assert committed["pending"] is None
            assert session.submitted == [SUBMIT_1, SUBMIT_2]
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_journal_write_preserves_transcript_revision_and_retains_signed_bytes(
    session_environment,
):
    data, authority = session_environment

    async def scenario():
        client = await connect(data, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            await session.reserve("message-1", "first")
            task_id = await session.submit_pending(SUBMIT_1)
            result, terminal = await client.wait_task(task_id, timeout_s=15)
            assert terminal and result["status"] == "SUCCEEDED", result
            observed_revision = session.revision
            envelope, committed = await session.register_writeback(WRITEBACK_1, result)
            # Registering the journal did not move the transcript CAS that the
            # prepared writeback command depends on.
            assert session.revision == observed_revision
            current = await session.observe_transcript()
            assert current == session.document
            previous_content = session.transcript["content_artifact_id"]
            receipt = await session.commit_writeback(envelope, committed)
            assert receipt.resource["content_artifact_id"] != previous_content
            stored = await session.observe_transcript()
            assert stored == committed
            journal = await session.observe_journal()
            assert [entry["stage"] for entry in journal["entries"]] == ["SUBMIT", "WRITEBACK"]
            for entry in journal["entries"]:
                raw = entry["command_jcs"]
                assert entry["command_sha256"] == sha256_hex(raw.encode("utf-8"))
            assert journal["entries"][1]["command_jcs"] == envelope
            replay = await client.execute_command(WRITEBACK_METHOD, envelope)
            assert replay.resource["cas_revision"] == session.revision[1]
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_model_projection_carries_only_current_input_without_control_fields(
    session_environment,
):
    data, authority = session_environment

    async def scenario():
        client = await connect(data, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            await session.reserve("message-1", "PROJECTION_CANARY")
            task_id = await session.submit_pending(SUBMIT_1)
            await session.complete_pending(WRITEBACK_1)
            execution = await client.get_task_execution(task_id)
            stored = execution["projections"][0]
            rendered = await client.get_artifact_content(stored["rendered_artifact_id"])
            sections = stored["manifest"]["sections"]
            bodies = rendered.split(SECTION_DELIMITER)
            assert [item["section_id"] for item in sections] == [
                "system",
                "task_input",
                "capability_schema",
                "state_summary",
                "facts",
            ]
            assert json.loads(bodies[1]) == message_input("PROJECTION_CANARY")
            assert rendered.count(b"PROJECTION_CANARY") == 1
            journal = await session.observe_journal()
            for entry in journal["entries"]:
                assert entry["command_jcs"].encode("utf-8") not in rendered
                assert entry["command_id"].encode("utf-8") not in rendered
                assert entry["command_sha256"].encode("utf-8") not in rendered
            for marker in (
                b"auth_signature",
                b"command_jcs",
                b"command_sha256",
                b'"pending"',
                b'"summary"',
                b"controller_id",
            ):
                assert marker not in rendered, marker
            # Host state-summary sections may reference observed revision
            # pointers, but the task_input body is exactly the coordinator's
            # current input: no control fields of any kind.
            assert b"state://" not in bodies[1] and b"task://" not in bodies[1]
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_external_transcript_conflict_stops_round_without_merge_or_redispatch(
    session_environment,
):
    data, authority = session_environment

    async def scenario():
        client = await connect(data, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            await session.reserve("message-1", "first")
            task_id = await session.submit_pending(SUBMIT_1)
            # An external writer resolves the same transcript independently.
            foreign = copy.deepcopy(session.document)
            foreign["pending"] = None
            content = await upload(client, authority, foreign)
            await client.write_state(
                realm_id=REALM, actor_id=authority.actor_id,
                state_id=session.transcript["state_id"],
                expected_state_revision_id=session.revision[0],
                expected_cas_revision=session.revision[1],
                schema_id=session.schema, content_artifact_id=content,
            )
            # Disconnecting never cancels the accepted Task.
            result, terminal = await client.wait_task(task_id, timeout_s=15)
            assert terminal and result["status"] == "SUCCEEDED", result
            envelope, committed = await session.register_writeback(WRITEBACK_1, result)
            with pytest.raises(StableError) as conflict:
                await session.commit_writeback(envelope, committed)
            assert conflict.value.code == "REVISION_CONFLICT"
            # The coordinator reports and stops: no merge, no append, no new Task.
            assert session.submitted == [SUBMIT_1]
            current = await session.observe_transcript()
            assert current == foreign
            # The journal now references a message the transcript lost; any
            # further coordination on this State must fail closed.
            with pytest.raises(ValueError, match="differs"):
                await session.observe_journal()
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_summary_provenance_commits_against_history_and_serving_stays_frozen(
    session_environment,
):
    data, authority = session_environment

    async def scenario():
        client = await connect(data, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            servings = []
            compositions = []
            for index, (submit_id, writeback_id) in enumerate(
                ((SUBMIT_1, WRITEBACK_1), (SUBMIT_2, WRITEBACK_2))
            ):
                await session.reserve(f"message-{index + 1}", f"round-{index + 1}")
                await session.submit_pending(submit_id)
                receipt = session.submit_receipts[-1]
                servings.append(receipt.resource["serving_revision"])
                task_id = receipt.resource["task_id"]
                trace = await client.get_task_trace(task_id)
                compositions.append(trace["actions"][0]["composition_id"])
                await session.complete_pending(writeback_id)
            assert servings[0] == servings[1] and servings[0] > 0
            assert compositions[0] == compositions[1]
            observed = await session.observe_transcript()
            source_revision = session.revision[0]
            provenance = committed_ids(observed["messages"][0])
            reference = "artifact://sha256/" + "7" * 64
            summarized = copy.deepcopy(observed)
            summarized["summary"] = {
                "covered_messages": [provenance],
                "content_artifact_id": reference,
                "renderer_artifact_id": reference,
                "tokenizer_artifact_id": reference,
                "redaction_policy_artifact_id": reference,
                "source_transcript_revision_id": source_revision,
            }
            validate_session(summarized)
            # The recorded source revision is real history that contains the
            # covered prefix, not a fabricated pointer.
            historical = await client.get_state(
                realm_id=REALM, actor_id=authority.actor_id,
                state_id=session.transcript["state_id"],
                state_revision_id=source_revision,
            )
            historical_document = json.loads(
                await client.get_artifact_content(historical["content_artifact_id"])
            )
            assert len(historical_document["messages"]) == 2
            assert committed_ids(historical_document["messages"][0]) == provenance
            await session.commit_document(summarized)
            context = session.session_context()
            assert context["summary"]["covered_messages"] == [provenance]
            assert context["messages"] == observed["messages"]
            projected = canonical_json(context)
            assert b'"pending"' not in projected and b"command_jcs" not in projected
            broken = copy.deepcopy(summarized)
            broken["summary"]["source_transcript_revision_id"] = "state-revision://" + "f" * 64
            with pytest.raises(ValueError):
                validate_session(broken)
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_identical_inputs_render_identical_projections_and_secrets_redact_before_ranking(
    session_environment,
):
    data, authority = session_environment

    async def scenario():
        client = await connect(data, authority=authority)
        try:
            session = await open_session(client, authority, SESSION_DOCUMENT)
            # The same logical input built in two different key orders is one
            # content-addressed Artifact: ordering cannot influence anything
            # downstream of admission.
            leaked = "sk-abcdef12345678 secret: SESS_SECRET_CANARY"
            first = {"provider": "fake", "scenario": "terminal", "value": leaked}
            second = {"value": leaked, "scenario": "terminal", "provider": "fake"}
            reference = await upload(client, authority, first)
            assert reference == await upload(client, authority, second)
            servings = []
            rendered_inputs = []
            for index, message in enumerate(("message-1", "message-2")):
                await session.reserve(message, input_artifact_id=reference)
                task_id = await session.submit_pending(
                    f"task://019a44d0-0000-7000-8000-0000000000{2 * index + 1:02d}"
                )
                servings.append(session.submit_receipts[-1].resource["serving_revision"])
                await session.complete_pending(
                    f"task://019a44d0-0000-7000-8000-0000000000{2 * index + 2:02d}"
                )
                execution = await client.get_task_execution(task_id)
                stored = execution["projections"][0]
                rendered = await client.get_artifact_content(stored["rendered_artifact_id"])
                rendered_inputs.append(rendered)
            # One frozen serving revision, byte-identical redacted model
            # input for identical inputs across distinct Tasks. Only the
            # Host-attached state/facts sections may carry session-scoped
            # revision pointers, which legitimately advance per round.
            assert servings[0] == servings[1] and servings[0] > 0
            section_bodies = [item.split(SECTION_DELIMITER) for item in rendered_inputs]
            assert [len(item) for item in section_bodies] == [5, 5]
            for index in range(3):
                assert section_bodies[0][index] == section_bodies[1][index]
            task_input = json.loads(section_bodies[0][1])
            assert task_input == json.loads(section_bodies[1][1])
            # Both string-level secret patterns were rewritten before the
            # budget ladder ranked anything, in canonical key order.
            assert task_input["value"] == "[REDACTED] [REDACTED]"
            assert b"SESS_SECRET_CANARY" not in rendered_inputs[0]
            assert b"sk-abcdef12345678" not in rendered_inputs[0]
            assert b"SESS_SECRET_CANARY" not in rendered_inputs[1]
            assert set(task_input) == {"provider", "scenario", "value"}
        finally:
            await client.aclose()

    asyncio.run(scenario())
