"""Minimal S06 session front-end (plan step 4/5) over public contracts only.

Each free-text line is one durable message round; the REPL generates stable
message identities, recovers a pending round on attach before admitting new
input, and explains any round's lineage from the transcript, the command
journal and the public Task trace. No new protocol surface is introduced:
every durable effect goes through the coordinator's signed public commands.
"""

from agent_meta_seed_harness.session import (
    SessionConflict,
    validate_journal,
    validate_session,
)
from agent_meta_seed_harness.session_coordinator import SessionCoordinator


def next_message_id(document):
    """Stable deterministic identity; identical state proposes the same id."""
    validate_session(document)
    used = {item["message_id"] for item in document["messages"]}
    if document["pending"]:
        used.add(document["pending"]["message_id"])
    index = 1
    while f"message-{index}" in used:
        index += 1
    return f"message-{index}"


def explain_round(document, journal, *, message_id, trace=None):
    """Assemble the bounded lineage of one round from committed documents.

    ``trace`` is the public Task trace for a committed round; only bounded,
    well-formed fields are copied. Pending rounds carry their reserved
    command identities instead of terminal fields.
    """
    validate_session(document)
    validate_journal(journal, document)
    committed = next(
        (item for item in document["messages"] if item["message_id"] == message_id),
        None,
    )
    pending = (
        document["pending"]
        if document["pending"] and document["pending"]["message_id"] == message_id
        else None
    )
    if committed is None and pending is None:
        raise SessionConflict("no committed or pending round for this message")
    source = committed or pending
    explanation = {
        "message_id": message_id,
        "state": "committed" if committed else "pending",
        "input_artifact_id": source["input_artifact_id"],
        "task_id": source["task_id"],
        "journal": [
            {
                "stage": entry["stage"],
                "method": entry["method"],
                "command_id": entry["command_id"],
                "command_sha256": entry["command_sha256"],
            }
            for entry in journal["entries"] if entry["message_id"] == message_id
        ],
    }
    if committed:
        explanation["terminal_status"] = committed["terminal_status"]
        explanation["result_artifact_id"] = committed["result_artifact_id"]
        if trace is not None:
            if (
                type(trace) is not dict
                or type(trace.get("actions")) is not list
                or not trace["actions"]
                or any(type(action) is not dict for action in trace["actions"])
                or "composition_id" not in trace["actions"][0]
            ):
                raise ValueError("malformed public Task trace")
            explanation["composition_id"] = trace["actions"][0]["composition_id"]
            explanation["actions"] = len(trace["actions"])
    else:
        explanation["submit_command_id"] = pending["submit_command_id"]
        explanation["writeback_command_id"] = pending["writeback_command_id"]
    return explanation


def render_explanation(explanation):
    """Bounded human lines for one round's lineage."""
    lines = [
        f"{explanation['message_id']} [{explanation['state']}] "
        f"task={explanation['task_id']} input={explanation['input_artifact_id']}"
    ]
    for entry in explanation["journal"]:
        lines.append(
            f"  {entry['stage']} {entry['command_id']} sha256={entry['command_sha256']}"
        )
    if explanation["state"] == "committed":
        lines.append(
            f"  terminal={explanation['terminal_status']} "
            f"result={explanation['result_artifact_id']}"
        )
        if "composition_id" in explanation:
            lines.append(
                f"  composition={explanation['composition_id']} "
                f"actions={explanation['actions']}"
            )
    else:
        lines.append(
            f"  submit={explanation['submit_command_id']} "
            f"writeback={explanation['writeback_command_id']}"
        )
    return lines


class SessionRepl:
    """Interactive front-end; one free-text line drives one message round."""

    def __init__(self, coordinator):
        if not isinstance(coordinator, SessionCoordinator):
            raise TypeError("the REPL drives a session coordinator")
        self.coordinator = coordinator
        self.stopped = False

    async def attach(self):
        """Recover any pending round before admitting new input."""
        return await self.coordinator.recover_pending()

    async def send(self, value):
        """Run one complete durable round for a new user message."""
        document = await self.coordinator.observe_transcript()
        message_id = next_message_id(document)
        await self.coordinator.reserve(message_id, value)
        await self.coordinator.submit_pending()
        receipt = await self.coordinator.complete_pending()
        return message_id, receipt

    async def explain(self, message_id):
        """Lineage for any round; committed rounds include the public trace."""
        document = await self.coordinator.observe_transcript()
        journal = await self.coordinator.observe_journal()
        explanation = explain_round(document, journal, message_id=message_id)
        if explanation["state"] == "committed" and explanation["task_id"]:
            trace = await self.coordinator.client.get_task_trace(explanation["task_id"])
            verified = explain_round(
                document, journal, message_id=message_id, trace=trace
            )
            explanation["composition_id"] = verified["composition_id"]
            explanation["actions"] = verified["actions"]
        return explanation

    async def _history(self):
        document = self.coordinator.document
        lines = []
        for item in document["messages"]:
            lines.append(
                f"{item['message_id']} {item['terminal_status']} "
                f"task={item['task_id']}"
            )
        if document["pending"]:
            lines.append(f"{document['pending']['message_id']} PENDING")
        return lines or ["(no messages yet)"]

    async def handle_line(self, line):
        """Return the bounded output lines for one interactive line."""
        text = line.strip()
        if not text:
            return []
        if text == "/quit":
            self.stopped = True
            return ["session closed; committed State is durable"]
        if text == "/history":
            return await self._history()
        if text.startswith("/explain "):
            return render_explanation(await self.explain(text[len("/explain "):].strip()))
        if text.startswith("/"):
            return [
                "commands: /history, /explain <message_id>, /quit; "
                "any other line sends one message"
            ]
        message_id, _ = await self.send(text)
        return [f"committed {message_id}"]

    async def run(self, reader, writer):
        """Loop until /quit or end of input; reader/writer are injectable."""
        await self.attach()
        while not self.stopped:
            line = await reader()
            if line is None:
                break
            for output in await self.handle_line(line):
                writer(output)
