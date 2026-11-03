"""S06 preparation only; durable recovery/activation are separate gates."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import (
    AgentMetaClient,
    CommandAuthority,
    decode_command,
    encode_command,
    sign_command,
)
from agent_meta_runtime.sdk.packages import canonical_json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent_meta_seed_harness.session import (
    JOURNAL_SCHEMA,
    SESSION_SCHEMA,
    SUBMIT,
    WRITEBACK,
    SessionConflict,
    completed_context,
    document_schema,
    register_command,
    reserve_message,
    validate_journal,
    validate_session,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/session"
UUID = "019a44d0-0000-7000-8000-000000000001"
INPUT = "artifact://sha256/" + "2" * 64


def fixture(name="empty-v1.json"):
    return json.loads((FIXTURES / name).read_bytes())


def command(
    document, *, stage="SUBMIT", number=1, payload_update=None, meta=None, signed=True
):
    # Offline, public DTO authoring only: this Transport is never called.
    client = AgentMetaClient(None)
    payload = (
        {"input_artifact_id": INPUT}
        if stage == "SUBMIT"
        else {
            "state_id": document["config"]["transcript_state_id"],
            "expected_state_revision_id": "state-revision://" + UUID,
            "expected_cas_revision": 3,
            "schema_id": "artifact://sha256/" + "3" * 64,
            "content_artifact_id": "artifact://sha256/" + "4" * 64,
        }
    )
    payload.update(payload_update or {})
    raw = client.build_envelope_jcs(
        realm_id="realm://main",
        actor_id=document["config"]["controller_id"],
        authority_grant_id="grant://" + UUID,
        expected_meta_revision=meta,
        command_id="task://019a44d0-0000-7000-8000-" + str(number).zfill(12),
        payload_type="task.submit/v1" if stage == "SUBMIT" else "state.write/v1",
        payload=payload,
    )
    if not signed:
        return raw
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    authority = CommandAuthority(
        document["config"]["controller_id"], "grant://" + UUID, key.sign
    )
    return encode_command(
        sign_command(
            decode_command(raw),
            authority,
            nonce="seed-session-public-fixture-000001",
            issued_at_us=1793664000000000,
        )
    )


def pending():
    return reserve_message(fixture(), "message-1", INPUT)


def journal():
    return fixture("journal-empty-v1.json")


def submitted():
    value = pending()
    value["pending"].update(
        task_id="task://" + UUID, submit_command_id="task://" + UUID
    )
    return value


def committed():
    value = fixture()
    value["messages"] = [
        {
            "message_id": "message-1",
            "input_artifact_id": INPUT,
            "task_id": "task://" + UUID,
            "terminal_status": "SUCCEEDED",
            "result_artifact_id": "artifact://sha256/" + "5" * 64,
        }
    ]
    return value


def test_frozen_schema_and_fixture_hashes_are_exact_installed_resources():
    manifest = fixture("manifest-v1.json")
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    for name in (SESSION_SCHEMA, JOURNAL_SCHEMA):
        assert canonical_json(document_schema(name)) == canonical_json(
            json.loads(
                (
                    ROOT / "src/agent_meta_seed_harness/schemas" / (name + ".json")
                ).read_bytes()
            )
        )
    assert validate_session(fixture()) == fixture()
    assert validate_journal(journal(), fixture()) == journal()
    with pytest.raises(ValueError, match="unsupported"):
        document_schema("seed/session/v2")


def test_message_retry_preserves_pending_or_completed_identity_without_input_mutation():
    original = fixture()
    value = reserve_message(original, "message-1", INPUT)
    assert original["pending"] is None
    assert reserve_message(value, "message-1", INPUT) == value
    done = committed()
    assert reserve_message(done, "message-1", INPUT) == done
    for existing in (value, done):
        with pytest.raises(SessionConflict, match="different input"):
            reserve_message(existing, "message-1", "artifact://sha256/" + "6" * 64)
    with pytest.raises(SessionConflict, match="already pending"):
        reserve_message(value, "message-2", INPUT)


def test_journal_is_separate_and_preserves_exact_signed_command_bytes():
    value = pending()
    before = canonical_json(value)
    raw = command(value)
    registered = register_command(
        journal(),
        value,
        message_id="message-1",
        stage="SUBMIT",
        method=SUBMIT,
        command_jcs=raw,
    )
    assert canonical_json(value) == before
    assert registered["entries"][0]["command_jcs"] == raw
    assert (
        registered["entries"][0]["command_sha256"]
        == hashlib.sha256(raw.encode()).hexdigest()
    )
    assert (
        register_command(
            registered,
            value,
            message_id="message-1",
            stage="SUBMIT",
            method=SUBMIT,
            command_jcs=raw,
        )
        == registered
    )
    with pytest.raises(SessionConflict, match="different command bytes"):
        register_command(
            registered,
            value,
            message_id="message-1",
            stage="SUBMIT",
            method=SUBMIT,
            command_jcs=command(value, number=2),
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"meta": 1},
        {"signed": False},
        {"payload_update": {"input_artifact_id": "artifact://sha256/" + "9" * 64}},
        {"payload_update": {"unexpected": "field"}},
        {"payload_update": {"budget": {"unknown": 1}}},
        {"payload_update": {"budget": {"max_turns": True}}},
        {"payload_update": {"budget": []}},
        {"payload_update": {"deadline_at_us": True}},
        {"payload_update": {"deadline_at_us": -1}},
    ],
)
def test_submit_refuses_meta_guard_unsigned_and_different_input(kwargs):
    value = pending()
    with pytest.raises(ValueError):
        register_command(
            journal(),
            value,
            message_id="message-1",
            stage="SUBMIT",
            method=SUBMIT,
            command_jcs=command(value, **kwargs),
        )


def test_writeback_retains_target_revision_and_requires_original_submit():
    value = submitted()
    raw_submit = command(value)
    first = register_command(
        journal(),
        value,
        message_id="message-1",
        stage="SUBMIT",
        method=SUBMIT,
        command_jcs=raw_submit,
    )
    raw = command(value, stage="WRITEBACK", number=2)
    result = register_command(
        first,
        value,
        message_id="message-1",
        stage="WRITEBACK",
        method=WRITEBACK,
        command_jcs=raw,
    )
    envelope = decode_command(result["entries"][1]["command_jcs"])
    assert envelope.payload["expected_cas_revision"] == 3
    assert envelope.payload["expected_state_revision_id"] == "state-revision://" + UUID
    assert envelope.payload["state_id"] != value["config"]["journal_state_id"]
    with pytest.raises(ValueError):
        register_command(
            journal(),
            value,
            message_id="message-1",
            stage="WRITEBACK",
            method=WRITEBACK,
            command_jcs=raw,
        )
    for update in (
        {"state_id": value["config"]["journal_state_id"]},
        {"expected_cas_revision": True},
    ):
        with pytest.raises(ValueError):
            register_command(
                first,
                value,
                message_id="message-1",
                stage="WRITEBACK",
                method=WRITEBACK,
                command_jcs=command(
                    value, stage="WRITEBACK", number=2, payload_update=update
                ),
            )


def test_journal_rejects_tampering_identity_and_wrong_session():
    value = pending()
    registered = register_command(
        journal(),
        value,
        message_id="message-1",
        stage="SUBMIT",
        method=SUBMIT,
        command_jcs=command(value),
    )
    for field, replacement in (
        ("command_sha256", "0" * 64),
        ("method", WRITEBACK),
        ("message_id", "foreign-message"),
        ("command_id", "task://019a44d0-0000-7000-8000-000000000002"),
    ):
        changed = copy.deepcopy(registered)
        changed["entries"][0][field] = replacement
        with pytest.raises(ValueError):
            validate_journal(changed, value)
    changed = copy.deepcopy(registered)
    changed["entries"].append(copy.deepcopy(changed["entries"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate_journal(changed, value)


def test_summary_requires_exact_committed_prefix_and_all_provenance():
    value = committed()
    value["summary"] = {
        "covered_messages": [
            {
                key: item
                for key, item in value["messages"][0].items()
                if key != "terminal_status"
            }
        ],
        **{
            key: "artifact://sha256/" + "7" * 64
            for key in (
                "content_artifact_id",
                "renderer_artifact_id",
                "tokenizer_artifact_id",
                "redaction_policy_artifact_id",
            )
        },
        "source_transcript_revision_id": "state-revision://" + UUID,
    }
    validate_session(value)
    for mutate in ("future", "missing", "nonprefix"):
        changed = copy.deepcopy(value)
        if mutate == "future":
            changed["summary"]["covered_messages"][0][
                "task_id"
            ] = "task://019a44d0-0000-7000-8000-000000000002"
        elif mutate == "missing":
            del changed["summary"]["tokenizer_artifact_id"]
        else:
            changed["summary"]["covered_messages"] = []
        with pytest.raises(ValueError):
            validate_session(changed)


def test_context_excludes_pending_control_journal_signatures_and_current_input():
    value = committed()
    value = reserve_message(value, "message-2", "artifact://sha256/" + "8" * 64)
    projected = completed_context(value)
    raw = canonical_json(projected)
    assert b"message-2" not in raw and ("8" * 64).encode() not in raw
    assert all(
        word not in raw
        for word in (
            b"pending",
            b"command",
            b"journal",
            b"controller",
            b"auth_signature",
        )
    )
    assert projected["messages"] == value["messages"]
    projected["messages"].clear()
    assert len(value["messages"]) == 1


def test_terminal_status_and_task_uniqueness_cannot_be_inferred_from_unknown_effect():
    for status in ("UNKNOWN", "RUNNING", "DISPATCHED"):
        value = committed()
        value["messages"][0]["terminal_status"] = status
        with pytest.raises(ValueError, match="terminal"):
            validate_session(value)
    value = committed()
    value["messages"][0]["result_artifact_id"] = None
    with pytest.raises(ValueError, match="committed result"):
        validate_session(value)
    for status in ("FAILED", "FAILED_RECOVERY", "CANCELLED", "TIMED_OUT"):
        value["messages"][0]["terminal_status"] = status
        validate_session(value)
    value = committed()
    value["messages"].append({**value["messages"][0], "message_id": "message-2"})
    with pytest.raises(ValueError, match="two messages"):
        validate_session(value)


def test_capacity_exhaustion_preserves_existing_transcript_and_journal():
    value = committed()
    original = value["messages"][0]
    value["messages"] = [
        {
            **original,
            "message_id": f"message-{index}",
            "task_id": "task://019a44d0-0000-7000-8000-" + str(index).zfill(12),
        }
        for index in range(128)
    ]
    validate_session(value)
    before = canonical_json(value)
    with pytest.raises(ValueError, match="ceiling"):
        reserve_message(value, "next-message", INPUT)
    assert canonical_json(value) == before


def test_pending_receipt_must_match_original_journal_identity():
    value = submitted()
    with pytest.raises(ValueError, match="pending command identity"):
        register_command(
            journal(),
            value,
            message_id="message-1",
            stage="SUBMIT",
            method=SUBMIT,
            command_jcs=command(value, number=2),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema="seed/session/v2"),
        lambda d: d.update(unknown="field"),
        lambda d: d["config"].update(
            journal_state_id=d["config"]["transcript_state_id"]
        ),
        lambda d: d["config"].update(controller_id="principal://agent/not-a-uuid"),
        lambda d: d.update(messages=[{"message_id": "incomplete"}]),
        lambda d: d["pending"].update(task_id="task://" + UUID),
        lambda d: d["pending"].update(journal_state_id="state://" + UUID),
    ],
)
def test_unknown_schema_malformed_identity_and_pending_order_fail_closed(mutation):
    value = pending()
    mutation(value)
    with pytest.raises(ValueError):
        validate_session(value)
