"""Consumer-side session coordinator (S06) over public SDK contracts only.

Drives the plan's message protocol: reserve pending via State CAS, journal
the exact signed Task.Submit bytes, dispatch once, record the receipt, wait
for the committed terminal, journal the writeback, then append once. Durable
command identities live in the journal; a restart recovers from committed
State only and never regenerates a journaled command identity.
"""

import copy
import json

from agent_meta_runtime.sdk import decode_command
from agent_meta_runtime.sdk.packages import canonical_json

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

SUBMIT_METHOD = "agent_meta.public.v1.Task.Submit"
WRITEBACK_METHOD = "agent_meta.public.v1.State.Write"
REALM = "realm://main"
OWNER = "capability://seed.echo"
PERMISSIONS = [
    "artifact.put",
    "task.submit",
    "task.cancel",
    "model.invoke",
    "capability.invoke",
    "state.read",
    "state.write",
]


def message_input(value, *, scenario="terminal"):
    """Bounded deterministic task input for the offline fake Provider."""
    return {"provider": "fake", "scenario": scenario, "value": value}


async def upload(client, authority, value, *, kind="seed_content"):
    return (
        await client.put_artifact(
            realm_id=REALM, actor_id=authority.actor_id,
            content=canonical_json(value),
            kind=kind, media_type="application/json",
        )
    )["artifact_id"]


class SessionCoordinator:
    """One bounded session driven through durable public commands only."""

    def __init__(self, client, authority, transcript, journal, *, schema, journal_schema):
        self.client = client
        self.authority = authority
        self.transcript = transcript
        self.journal = journal
        self.schema = schema
        self.journal_schema = journal_schema
        self.submitted = []
        self.submit_receipts = []
        self.document = None
        self._revision = None
        self.journal_state = None
        self._journal_revision = None

    @property
    def revision(self):
        return self._revision

    async def observe_transcript(self):
        state = await self.client.get_state(
            realm_id=REALM, actor_id=self.authority.actor_id,
            state_id=self.transcript["state_id"],
        )
        document = json.loads(await self.client.get_artifact_content(state["content_artifact_id"]))
        validate_session(document)
        self.transcript, self.document = state, document
        self._revision = (state["state_revision_id"], state["cas_revision"])
        return document

    async def observe_journal(self):
        assert self.document is not None, "observe the transcript first"
        state = await self.client.get_state(
            realm_id=REALM, actor_id=self.authority.actor_id,
            state_id=self.journal["state_id"],
        )
        value = json.loads(await self.client.get_artifact_content(state["content_artifact_id"]))
        validate_journal(value, self.document)
        self.journal, self.journal_state = state, value
        self._journal_revision = (state["state_revision_id"], state["cas_revision"])
        return value

    async def _write_transcript(self, document, *, envelope=None):
        reference = await upload(self.client, self.authority, document)
        if envelope is None:
            receipt = await self.client.write_state(
                realm_id=REALM, actor_id=self.authority.actor_id,
                state_id=self.transcript["state_id"],
                expected_state_revision_id=self._revision[0],
                expected_cas_revision=self._revision[1],
                schema_id=self.schema, content_artifact_id=reference,
            )
        else:
            receipt = await self.client.execute_command(WRITEBACK_METHOD, envelope)
        resource = receipt.resource
        self.transcript = {
            **self.transcript,
            "state_revision_id": resource["state_revision_id"],
            "cas_revision": resource["cas_revision"],
            "content_artifact_id": resource["content_artifact_id"],
        }
        self._revision = (resource["state_revision_id"], resource["cas_revision"])
        self.document = document
        return receipt

    async def _write_journal(self, registered):
        reference = await upload(self.client, self.authority, registered)
        receipt = await self.client.write_state(
            realm_id=REALM, actor_id=self.authority.actor_id,
            state_id=self.journal["state_id"],
            expected_state_revision_id=self._journal_revision[0],
            expected_cas_revision=self._journal_revision[1],
            schema_id=self.journal_schema, content_artifact_id=reference,
        )
        resource = receipt.resource
        self.journal = {
            **self.journal,
            "state_revision_id": resource["state_revision_id"],
            "cas_revision": resource["cas_revision"],
            "content_artifact_id": resource["content_artifact_id"],
        }
        self._journal_revision = (resource["state_revision_id"], resource["cas_revision"])
        self.journal_state = registered
        return receipt

    async def reserve(self, message_id, value, *, scenario="terminal"):
        """Persist pending before any dispatch; identical retries change nothing."""
        document = await self.observe_transcript()
        reference = await upload(
            self.client, self.authority, message_input(value, scenario=scenario),
            kind="task_input",
        )
        pending = reserve_message(document, message_id, reference)
        if pending == document:
            return document
        await self._write_transcript(pending)
        return pending

    async def journal_submit(self, submit_id=None):
        """Journal the exact signed Task.Submit bytes before any dispatch.

        Without an explicit identity the public SDK generates the stable
        ``task://<UUIDv7>`` command id inside the signed envelope bytes.
        """
        document = self.document
        envelope = self.client.build_envelope_jcs(
            realm_id=REALM, actor_id=self.authority.actor_id,
            payload_type="task.submit/v1",
            payload={"input_artifact_id": document["pending"]["input_artifact_id"]},
            command_id=submit_id,
        )
        journal = await self.observe_journal()
        registered = register_command(
            journal, document, message_id=document["pending"]["message_id"],
            stage="SUBMIT", method=SUBMIT, command_jcs=envelope,
        )
        if registered != journal:
            await self._write_journal(registered)
        return envelope

    async def recover_pending_dispatch(self, message_id):
        """Recover the durable journaled submit bytes after an ambiguous write.

        Journal-write response loss is resolved by an audited read of the
        original message/stage entry; the exact registered bytes are replayed,
        never regenerated, and a genuinely missing entry fails this lookup.
        """
        journal = await self.observe_journal()
        entries = [
            entry for entry in journal["entries"]
            if entry["message_id"] == message_id and entry["stage"] == "SUBMIT"
        ]
        if len(entries) != 1:
            raise SessionConflict(
                "journal does not hold exactly one durable submit entry"
            )
        return entries[0]["command_jcs"]

    async def record_receipt(self, task_id, submit_id):
        """Write the accepted Task receipt back into the pending item."""
        coordinated = copy.deepcopy(self.document)
        coordinated["pending"]["task_id"] = task_id
        coordinated["pending"]["submit_command_id"] = submit_id
        validate_session(coordinated)
        await self._write_transcript(coordinated)

    async def submit_pending(self, submit_id=None):
        """Journal first, dispatch the exact bytes once, then record the receipt."""
        envelope = await self.journal_submit(submit_id)
        receipt = await self.client.execute_command(SUBMIT_METHOD, envelope)
        task_id = receipt.resource["task_id"]
        self.submitted.append(decode_command(envelope).command_id)
        self.submit_receipts.append(receipt)
        await self.record_receipt(task_id, decode_command(envelope).command_id)
        return task_id

    async def register_writeback(self, writeback_id, result):
        """Journal the append command before touching the transcript State.

        The terminal outcome comes from Task.Wait, never from the pending
        item: pending only ever carries submit/writeback command identities.
        """
        document = self.document
        pending = document["pending"]
        committed = copy.deepcopy(document)
        committed["pending"] = None
        committed["messages"].append({
            "message_id": pending["message_id"],
            "input_artifact_id": pending["input_artifact_id"],
            "task_id": pending["task_id"],
            "terminal_status": result["status"],
            # Non-terminal outcomes report an empty reference, not None.
            "result_artifact_id": result.get("result_artifact_id") or None,
        })
        validate_session(committed)
        reference = await upload(self.client, self.authority, committed)
        envelope = self.client.build_envelope_jcs(
            realm_id=REALM, actor_id=self.authority.actor_id,
            payload_type="state.write/v1",
            payload={
                "state_id": self.transcript["state_id"],
                "expected_state_revision_id": self._revision[0],
                "expected_cas_revision": self._revision[1],
                "schema_id": self.schema,
                "content_artifact_id": reference,
            },
            command_id=writeback_id,
        )
        journal = await self.observe_journal()
        registered = register_command(
            journal, committed, message_id=pending["message_id"],
            stage="WRITEBACK", method=WRITEBACK, command_jcs=envelope,
        )
        if registered != journal:
            await self._write_journal(registered)
        return envelope, committed

    async def commit_writeback(self, envelope, committed):
        receipt = await self._write_transcript(committed, envelope=envelope)
        return receipt

    async def complete_pending(self, writeback_id=None):
        """Terminal first, then journal, then one transcript append."""
        result, terminal = await self.client.wait_task(
            self.document["pending"]["task_id"], timeout_s=15
        )
        assert terminal, result
        envelope, committed = await self.register_writeback(writeback_id, result)
        return await self.commit_writeback(envelope, committed)

    async def recover_pending(self, *, writeback_id=None):
        """Recover a pending round from committed State before new admission.

        Restart order is pending first: an unjournaled pending message is
        submitted as a new durable identity; an ambiguous or accepted submit
        replays the exact journaled bytes; an observed receipt only waits for
        the terminal. ``None`` when nothing is pending.
        """
        document = await self.observe_transcript()
        pending = document["pending"]
        if pending is None:
            return None
        journal = await self.observe_journal()
        if pending["task_id"] is None and any(
            entry["message_id"] == pending["message_id"] and entry["stage"] == "SUBMIT"
            for entry in journal["entries"]
        ):
            envelope = await self.recover_pending_dispatch(pending["message_id"])
            receipt = await self.client.execute_command(SUBMIT_METHOD, envelope)
            command_id = decode_command(envelope).command_id
            await self.record_receipt(receipt.resource["task_id"], command_id)
        elif pending["task_id"] is None:
            await self.submit_pending()
        await self.complete_pending(writeback_id)
        return await self.observe_transcript()

    async def commit_document(self, document):
        """CAS-commit an independently prepared transcript document."""
        await self.observe_transcript()
        validate_session(document)
        return await self._write_transcript(document)

    def session_context(self):
        return completed_context(self.document)


async def open_session(client, authority, document):
    """Create the bound transcript/journal States from an initial document."""
    document = validate_session({
        **document,
        "config": {**document["config"], "controller_id": authority.actor_id},
    })
    schema = await upload(client, authority, document_schema(SESSION_SCHEMA), kind="schema")
    journal_schema = await upload(client, authority, document_schema(JOURNAL_SCHEMA), kind="schema")
    transcript = (
        await client.create_state(
            realm_id=REALM, actor_id=authority.actor_id, owner_id=OWNER,
            state_id=document["config"]["transcript_state_id"], schema_id=schema,
            content_artifact_id=await upload(client, authority, document),
            purpose="SESSION_TRANSCRIPT",
        )
    ).resource
    journal_document = {
        "schema": JOURNAL_SCHEMA,
        "session_id": document["session_id"],
        "entries": [],
    }
    journal = (
        await client.create_state(
            realm_id=REALM, actor_id=authority.actor_id, owner_id=OWNER,
            state_id=document["config"]["journal_state_id"], schema_id=journal_schema,
            content_artifact_id=await upload(client, authority, journal_document),
            purpose="SESSION_JOURNAL",
        )
    ).resource
    return SessionCoordinator(
        client, authority, transcript, journal, schema=schema, journal_schema=journal_schema
    )


async def reattach(client, authority, coordinator):
    """Rebind a coordinator to restarted daemon state from committed State only."""
    transcript = await client.get_state(
        realm_id=REALM, actor_id=authority.actor_id,
        state_id=coordinator.transcript["state_id"],
    )
    journal = await client.get_state(
        realm_id=REALM, actor_id=authority.actor_id,
        state_id=coordinator.journal["state_id"],
    )
    return SessionCoordinator(
        client, authority, transcript, journal,
        schema=coordinator.schema, journal_schema=coordinator.journal_schema,
    )
