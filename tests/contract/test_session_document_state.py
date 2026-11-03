"""Native public State proof for prepared schemas, not a session controller.

No Task is submitted. This verifies that Root accepts the frozen schema and
retains signed journal bytes, and a journal write cannot expire transcript CAS.
"""

import asyncio
import copy
import json
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import (
    StableError,
    connect,
    decode_command,
    encode_command,
    sign_command,
)
from agent_meta_seed_harness.session import (
    JOURNAL_SCHEMA,
    SESSION_SCHEMA,
    SUBMIT,
    document_schema,
    register_command,
    reserve_message,
    validate_journal,
    validate_session,
)
from contract.test_public_state_management import (
    REALM,
    OWNER,
    state_environment,
    upload,
)


def test_native_protected_documents_retain_command_bytes_and_independent_cas(
    state_environment,
):
    data, authority = state_environment

    async def run():
        client = await connect(data, authority=authority)
        try:
            fixture = (
                Path(__file__).resolve().parents[1] / "fixtures/session/empty-v1.json"
            )
            document = json.loads(fixture.read_bytes())
            document["config"]["controller_id"] = authority.actor_id
            schema = await upload(
                client, authority, document_schema(SESSION_SCHEMA), kind="schema"
            )
            journal_schema = await upload(
                client, authority, document_schema(JOURNAL_SCHEMA), kind="schema"
            )
            content = await upload(client, authority, document)
            transcript = (
                await client.create_state(
                    realm_id=REALM,
                    actor_id=authority.actor_id,
                    owner_id=OWNER,
                    state_id=document["config"]["transcript_state_id"],
                    schema_id=schema,
                    content_artifact_id=content,
                    purpose="SESSION_TRANSCRIPT",
                )
            ).resource
            empty = {
                "schema": JOURNAL_SCHEMA,
                "session_id": document["session_id"],
                "entries": [],
            }
            journal_content = await upload(client, authority, empty)
            journal = (
                await client.create_state(
                    realm_id=REALM,
                    actor_id=authority.actor_id,
                    owner_id=OWNER,
                    state_id=document["config"]["journal_state_id"],
                    schema_id=journal_schema,
                    content_artifact_id=journal_content,
                    purpose="SESSION_JOURNAL",
                )
            ).resource
            input_ref = await upload(
                client,
                authority,
                {"value": "offline schema fixture"},
                kind="task_input",
            )
            pending = reserve_message(document, "message-1", input_ref)
            pending_ref = await upload(client, authority, pending)
            transcript = (
                await client.write_state(
                    realm_id=REALM,
                    actor_id=authority.actor_id,
                    state_id=transcript["state_id"],
                    expected_state_revision_id=transcript["state_revision_id"],
                    expected_cas_revision=1,
                    schema_id=schema,
                    content_artifact_id=pending_ref,
                )
            ).resource
            submit = client.build_envelope_jcs(
                realm_id=REALM,
                actor_id=authority.actor_id,
                payload_type="task.submit/v1",
                payload={"input_artifact_id": input_ref},
            )
            submit = encode_command(
                sign_command(
                    decode_command(submit),
                    authority,
                    nonce="seed-session-document-control-0001",
                )
            )
            registered = register_command(
                empty,
                pending,
                message_id="message-1",
                stage="SUBMIT",
                method=SUBMIT,
                command_jcs=submit,
            )
            coordinated = copy.deepcopy(pending)
            coordinated["pending"]["submit_command_id"] = decode_command(
                submit
            ).command_id
            validate_session(coordinated)
            coordinated_ref = await upload(client, authority, coordinated)
            # Prepare this transcript command BEFORE committing another State.
            transcript_write = client.build_state_write(
                realm_id=REALM,
                actor_id=authority.actor_id,
                state_id=transcript["state_id"],
                expected_state_revision_id=transcript["state_revision_id"],
                expected_cas_revision=2,
                schema_id=schema,
                content_artifact_id=coordinated_ref,
            )
            registered_ref = await upload(client, authority, registered)
            written = (
                await client.write_state(
                    realm_id=REALM,
                    actor_id=authority.actor_id,
                    state_id=journal["state_id"],
                    expected_state_revision_id=journal["state_revision_id"],
                    expected_cas_revision=1,
                    schema_id=journal_schema,
                    content_artifact_id=registered_ref,
                )
            ).resource
            retained = json.loads(
                await client.get_artifact_content(written["content_artifact_id"])
            )
            validate_journal(retained, coordinated)
            assert retained == registered
            assert retained["entries"][0]["command_jcs"] == submit
            before = await client.get_state(
                realm_id=REALM,
                actor_id=authority.actor_id,
                state_id=transcript["state_id"],
            )
            assert (
                before["state_revision_id"] == transcript["state_revision_id"]
                and before["cas_revision"] == 2
            )
            receipt = await client.execute_command(
                "agent_meta.public.v1.State.Write", transcript_write
            )
            assert receipt.resource["cas_revision"] == 3
            assert (
                json.loads(
                    await client.get_artifact_content(
                        receipt.resource["content_artifact_id"]
                    )
                )
                == coordinated
            )
            assert (
                await client.execute_command(
                    "agent_meta.public.v1.State.Write", transcript_write
                )
                == receipt
            )
            for invalid in (
                {**coordinated, "unexpected": True},
                {**coordinated, "schema": "seed/session/v2"},
            ):
                invalid_ref = await upload(client, authority, invalid)
                with pytest.raises(StableError) as rejected:
                    await client.write_state(
                        realm_id=REALM,
                        actor_id=authority.actor_id,
                        state_id=transcript["state_id"],
                        expected_state_revision_id=receipt.resource[
                            "state_revision_id"
                        ],
                        expected_cas_revision=3,
                        schema_id=schema,
                        content_artifact_id=invalid_ref,
                    )
                assert rejected.value.code == "INVALID_ARGUMENT"
            current = await client.get_state(
                realm_id=REALM,
                actor_id=authority.actor_id,
                state_id=transcript["state_id"],
            )
            assert current["cas_revision"] == 3
        finally:
            await client.aclose()

    asyncio.run(run())


def test_redacted_signed_command_stops_recovery_instead_of_resigning(state_environment):
    data, authority = state_environment

    async def run():
        client = await connect(data, authority=authority)
        try:
            fixture = (
                Path(__file__).resolve().parents[1] / "fixtures/session/empty-v1.json"
            )
            document = json.loads(fixture.read_bytes())
            document["config"]["controller_id"] = authority.actor_id
            schema = await upload(
                client, authority, document_schema(JOURNAL_SCHEMA), kind="schema"
            )
            input_ref = await upload(
                client, authority, {"value": "never dispatched"}, kind="task_input"
            )
            pending = reserve_message(document, "message-1", input_ref)
            raw = client.build_envelope_jcs(
                realm_id=REALM,
                actor_id=authority.actor_id,
                payload_type="task.submit/v1",
                payload={"input_artifact_id": input_ref},
            )
            # A non-secret test nonce deliberately matches the Root policy.
            raw = encode_command(
                sign_command(decode_command(raw), authority, nonce="sk_" + "A" * 40)
            )
            empty = {
                "schema": JOURNAL_SCHEMA,
                "session_id": document["session_id"],
                "entries": [],
            }
            candidate = register_command(
                empty,
                pending,
                message_id="message-1",
                stage="SUBMIT",
                method=SUBMIT,
                command_jcs=raw,
            )
            content = await upload(client, authority, candidate)
            created = (
                await client.create_state(
                    realm_id=REALM,
                    actor_id=authority.actor_id,
                    owner_id=OWNER,
                    state_id=document["config"]["journal_state_id"],
                    schema_id=schema,
                    content_artifact_id=content,
                    purpose="SESSION_JOURNAL",
                )
            ).resource
            retained = json.loads(
                await client.get_artifact_content(created["content_artifact_id"])
            )
            assert retained["entries"][0]["command_jcs"] != raw
            assert "[REDACTED]" in retained["entries"][0]["command_jcs"]
            with pytest.raises(ValueError, match="hash or authorization"):
                validate_journal(retained, pending)
            # No Task.Submit or replacement command is executed in this test.
        finally:
            await client.aclose()

    asyncio.run(run())
