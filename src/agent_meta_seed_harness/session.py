"""Pure S06 document preparation; no Task dispatch or State writes.

These transitions do not authorize input references or verify signatures.
The future coordinator must check the serving Composition, protected State
purposes, Artifact/redaction provenance and committed receipts through SDK.
"""

from __future__ import annotations

import hashlib
from importlib.resources import files
import json
import re
import uuid

from agent_meta_runtime.sdk import decode_command
from agent_meta_runtime.sdk.host import TaskBudget
from agent_meta_runtime.sdk.packages import canonical_json


SESSION_SCHEMA = "seed/session/v1"
JOURNAL_SCHEMA = "seed/session-command-journal/v1"
TERMINAL = ("SUCCEEDED", "FAILED", "FAILED_RECOVERY", "TIMED_OUT", "CANCELLED")
MAX_MESSAGES = 128
MAX_DOCUMENT_BYTES = 512 * 1024
SUBMIT = "agent_meta.public.v1.Task.Submit"
WRITEBACK = "agent_meta.public.v1.State.Write"


class SessionConflict(ValueError):
    """Stop coordination; callers must not automatically merge or redispatch."""


def document_schema(name):
    """Load a frozen Seed schema from the installed distribution."""
    if name not in (SESSION_SCHEMA, JOURNAL_SCHEMA):
        raise ValueError("unsupported session document schema")
    return json.loads(
        files("agent_meta_seed_harness")
        .joinpath("schemas/" + name + ".json")
        .read_bytes()
    )


def _object(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError("session document has missing or unknown fields")


def _text(value, maximum=128):
    if (
        type(value) is not str
        or not 1 <= len(value) <= maximum
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("invalid bounded session text")


def _artifact(value, *, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not str or not re.fullmatch(
        r"artifact://sha256/[0-9a-f]{64}", value
    ):
        raise ValueError("session requires a canonical Artifact reference")


def _identity(value, prefix, *, nullable=False):
    if nullable and value is None:
        return
    _text(value, 255)
    if not value.startswith(prefix):
        raise ValueError("invalid session identity")
    suffix = value[len(prefix) :]
    if prefix == "realm://":
        if len(suffix) > 128 or not re.fullmatch(
            r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", suffix
        ):
            raise ValueError("invalid Realm identity")
        return
    if prefix == "principal://":
        kind, separator, suffix = suffix.partition("/")
        if not separator or kind not in (
            "operator-root",
            "agent",
            "capability",
            "service",
            "peer",
        ):
            raise ValueError("invalid controller principal")
    parsed = uuid.UUID(suffix)
    if str(parsed) != suffix or parsed.version != 7 or parsed.variant != uuid.RFC_4122:
        raise ValueError("session identity requires canonical UUIDv7")


def _copy(value):
    raw = canonical_json(value)
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("session document exceeds byte ceiling")
    return json.loads(raw)


def validate_session(value):
    _object(value, "schema session_id config messages summary pending")
    if value["schema"] != SESSION_SCHEMA:
        raise ValueError(
            "unsupported session schema; migration requires explicit approval"
        )
    _identity(value["session_id"], "session://")
    config = value["config"]
    _object(
        config,
        "realm_id controller_id composition_id transcript_state_id journal_state_id policy_artifact_id",
    )
    for key, prefix in (
        ("realm_id", "realm://"),
        ("controller_id", "principal://"),
        ("composition_id", "composition://"),
        ("transcript_state_id", "state://"),
        ("journal_state_id", "state://"),
    ):
        _identity(config[key], prefix)
    if config["transcript_state_id"] == config["journal_state_id"]:
        raise ValueError("transcript and journal must be separate States")
    _artifact(config["policy_artifact_id"])
    messages = value["messages"]
    if type(messages) is not list or len(messages) > MAX_MESSAGES:
        raise ValueError("session message ceiling exceeded")
    seen, tasks = set(), set()
    for item in messages:
        _object(
            item,
            "message_id input_artifact_id task_id terminal_status result_artifact_id",
        )
        _text(item["message_id"])
        if item["message_id"] in seen:
            raise ValueError("duplicate committed message")
        seen.add(item["message_id"])
        _artifact(item["input_artifact_id"])
        _identity(item["task_id"], "task://")
        if item["task_id"] in tasks:
            raise ValueError("one Task cannot represent two messages")
        tasks.add(item["task_id"])
        if item["terminal_status"] not in TERMINAL:
            raise ValueError("only committed terminal Tasks belong in transcript")
        _artifact(item["result_artifact_id"], nullable=True)
        if (
            item["terminal_status"] == "SUCCEEDED"
            and item["result_artifact_id"] is None
        ):
            raise ValueError("successful Task must reference its committed result")
    pending = value["pending"]
    if pending is not None:
        _object(
            pending,
            "message_id input_artifact_id task_id submit_command_id writeback_command_id journal_state_id",
        )
        _text(pending["message_id"])
        if pending["message_id"] in seen or len(messages) == MAX_MESSAGES:
            raise ValueError("pending message duplicates transcript or exceeds ceiling")
        _artifact(pending["input_artifact_id"])
        for key, prefix in (
            ("task_id", "task://"),
            ("submit_command_id", "task://"),
            ("writeback_command_id", "task://"),
        ):
            _identity(pending[key], prefix, nullable=True)
        if pending["journal_state_id"] != config["journal_state_id"]:
            raise ValueError("pending journal differs from approved configuration")
        if pending["task_id"] is not None and pending["submit_command_id"] is None:
            raise ValueError("Task receipt requires a durable submit command identity")
        if pending["task_id"] in tasks:
            raise ValueError("pending Task is already committed")
        if pending["writeback_command_id"] is not None and pending["task_id"] is None:
            raise ValueError("writeback cannot precede Task receipt")
    summary = value["summary"]
    if summary is not None:
        _object(
            summary,
            "covered_messages content_artifact_id renderer_artifact_id tokenizer_artifact_id redaction_policy_artifact_id source_transcript_revision_id",
        )
        covered = summary["covered_messages"]
        if type(covered) is not list or not covered or len(covered) > len(messages):
            raise ValueError("summary must cover a nonempty committed prefix")
        expected = [
            {
                key: item[key]
                for key in (
                    "message_id",
                    "input_artifact_id",
                    "task_id",
                    "result_artifact_id",
                )
            }
            for item in messages[: len(covered)]
        ]
        if covered != expected:
            raise ValueError("summary provenance differs from committed message prefix")
        for key in (
            "content_artifact_id",
            "renderer_artifact_id",
            "tokenizer_artifact_id",
            "redaction_policy_artifact_id",
        ):
            _artifact(summary[key])
        _identity(summary["source_transcript_revision_id"], "state-revision://")
    _copy(value)
    return value


def reserve_message(document, message_id, input_artifact_id):
    """Prepare a pending CAS value; retries preserve original Task identity."""
    validate_session(document)
    _text(message_id)
    _artifact(input_artifact_id)
    for item in [
        *document["messages"],
        *([document["pending"]] if document["pending"] else []),
    ]:
        if item["message_id"] == message_id:
            if item["input_artifact_id"] != input_artifact_id:
                raise SessionConflict(
                    "message identity already binds a different input"
                )
            return _copy(document)
    if document["pending"] is not None:
        raise SessionConflict("one message is already pending")
    result = _copy(document)
    result["pending"] = dict(
        message_id=message_id,
        input_artifact_id=input_artifact_id,
        task_id=None,
        submit_command_id=None,
        writeback_command_id=None,
        journal_state_id=document["config"]["journal_state_id"],
    )
    validate_session(result)
    return result


def completed_context(document):
    """Allowlist only committed history; current input is supplied separately."""
    validate_session(document)
    return _copy(
        {
            "schema": "seed/session-context/v1",
            "session_id": document["session_id"],
            "policy_artifact_id": document["config"]["policy_artifact_id"],
            "messages": document["messages"],
            "summary": document["summary"],
        }
    )


def validate_journal(value, document):
    """Check replay identity/target, not signature validity or authorization."""
    validate_session(document)
    _object(value, "schema session_id entries")
    if (
        value["schema"] != JOURNAL_SCHEMA
        or value["session_id"] != document["session_id"]
    ):
        raise ValueError("journal schema/session differs")
    entries = value["entries"]
    if type(entries) is not list or len(entries) > 2 * MAX_MESSAGES:
        raise ValueError("journal entry ceiling exceeded")
    seen, commands = set(), set()
    known = {item["message_id"]: item for item in document["messages"]}
    if document["pending"]:
        known[document["pending"]["message_id"]] = document["pending"]
    for entry in entries:
        _object(entry, "message_id stage method command_id command_sha256 command_jcs")
        _text(entry["message_id"])
        _identity(entry["command_id"], "task://")
        if entry["stage"] not in ("SUBMIT", "WRITEBACK"):
            raise ValueError("unknown session command stage")
        key = (entry["message_id"], entry["stage"])
        if key in seen or entry["command_id"] in commands:
            raise ValueError("duplicate journal identity")
        seen.add(key)
        commands.add(entry["command_id"])
        raw = entry["command_jcs"]
        if type(raw) is not str or len(raw.encode("utf-8")) > 16 * 1024:
            raise ValueError("journal command exceeds ceiling")
        command = decode_command(raw)
        config = document["config"]
        message = known.get(entry["message_id"])
        if (
            message is None
            or command.command_id != entry["command_id"]
            or hashlib.sha256(raw.encode("utf-8")).hexdigest()
            != entry["command_sha256"]
            or command.realm_id != config["realm_id"]
            or command.actor_id != config["controller_id"]
            or command.expected_meta_revision is not None
            or command.payload_schema_version != 1
            or command.auth_signature is None
            or type(command.auth_nonce) is not str
            or not 1 <= len(command.auth_nonce) <= 256
            or command.authority_grant_id is None
            or type(command.auth_issued_at_us) is not int
            or command.auth_issued_at_us <= 0
        ):
            raise ValueError(
                "journal command identity, hash or authorization representation differs"
            )
        if entry["stage"] == "SUBMIT":
            if (
                entry["method"] != SUBMIT
                or command.payload_type != "task.submit/v1"
                or set(command.payload)
                - {"input_artifact_id", "budget", "deadline_at_us"}
                or command.payload.get("input_artifact_id")
                != message["input_artifact_id"]
            ):
                raise ValueError("journal submit differs from reserved input")
            budget = command.payload.get("budget", {})
            if type(budget) is not dict:
                raise ValueError(
                    "journal Task budget must use the public scalar contract"
                )
            try:
                TaskBudget(**budget)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "journal Task budget violates the public contract"
                ) from exc
            deadline = command.payload.get("deadline_at_us")
            if deadline is not None and (type(deadline) is not int or deadline < 0):
                raise ValueError("journal Task deadline violates the public contract")
        else:
            payload = command.payload
            if (
                entry["method"] != WRITEBACK
                or command.payload_type != "state.write/v1"
                or set(payload)
                != {
                    "state_id",
                    "expected_state_revision_id",
                    "expected_cas_revision",
                    "schema_id",
                    "content_artifact_id",
                }
                or payload["state_id"] != config["transcript_state_id"]
                or message["task_id"] is None
                or (entry["message_id"], "SUBMIT") not in seen
                or type(payload["expected_cas_revision"]) is not int
                or payload["expected_cas_revision"] < 1
            ):
                raise ValueError(
                    "journal writeback must target the transcript with explicit CAS"
                )
            _identity(payload["expected_state_revision_id"], "state-revision://")
            _artifact(payload["schema_id"])
            _artifact(payload["content_artifact_id"])
        if message is document["pending"]:
            declared = message[
                (
                    "submit_command_id"
                    if entry["stage"] == "SUBMIT"
                    else "writeback_command_id"
                )
            ]
            if declared is not None and declared != command.command_id:
                raise ValueError(
                    "pending command identity differs from durable journal"
                )
    _copy(value)
    return value


def register_command(journal, document, *, message_id, stage, method, command_jcs):
    """Prepare the *separate journal* CAS value, retaining exact signed bytes."""
    validate_journal(journal, document)
    if type(command_jcs) is not str or len(command_jcs.encode("utf-8")) > 16 * 1024:
        raise ValueError("journal command requires bounded canonical text")
    command = decode_command(command_jcs)
    entry = dict(
        message_id=message_id,
        stage=stage,
        method=method,
        command_id=command.command_id,
        command_sha256=hashlib.sha256(command_jcs.encode("utf-8")).hexdigest(),
        command_jcs=command_jcs,
    )
    result = _copy(journal)
    for existing in result["entries"]:
        if (existing["message_id"], existing["stage"]) == (message_id, stage):
            if existing != entry:
                raise SessionConflict(
                    "journal key already binds different command bytes"
                )
            return result
    result["entries"].append(entry)
    validate_journal(result, document)
    return result
