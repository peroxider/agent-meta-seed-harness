# Session document preparation

This is advance schema/fixture work permitted by the development handoff.
S05, RP-04 and RP-05 remain open. There is no session activation profile,
coordinator or REPL yet; these functions do not submit Tasks or write State.
The existing minimal/tools execution packages do not include `session.py`.

The installed distribution contains two immutable Seed application schemas:

- `schemas/seed/session/v1.json`: configuration, ordered terminal messages,
  an optional provenance-bearing summary and at most one pending message.
- `schemas/seed/session-command-journal/v1.json`: the exact public method and
  signed canonical command bytes, keyed by message and submit/writeback stage.

These are JSON content schemas for public Managed State, not new Runtime
entities. JSON Schema uses only the supported public State subset. The pure
`session.py` validators additionally enforce identity, uniqueness, sequencing,
reference and provenance invariants that this subset cannot express.

`tests/fixtures/session/manifest-v1.json` freezes both schemas and initial
documents by SHA-256. Unknown fields and versions fail closed. The v1 profile
allows 128 committed messages, 256 journal entries and 512 KiB per document;
capacity exhaustion requires an explicit new-session transition, not silent
history deletion or automatic journal compaction.

## Configuration and authority

Configuration records a session UUID, Realm, controller principal, approved
Composition, distinct transcript/journal State IDs and a policy Artifact.
Root purposes must be `SESSION_TRANSCRIPT` and `SESSION_JOURNAL`. A future
controller must verify these values against the actual serving Composition
and audited public State snapshots before admission. A configuration document
or user-supplied State ID is not evidence of a binding or grant.

Input/result references must already point to authorized, policy-redacted
Artifacts. Syntax validation cannot establish their content, policy lineage,
ownership or access rights. The controller must obtain those facts through
public Runtime contracts. It must not copy a private Runtime redactor into Seed
or accept a caller's assertion that content is safe.

## Durable commands and recovery

`reserve_message` prepares a new transcript value without modifying its input.
The same message/input preserves the original pending or terminal identity;
a different input for that message or a second pending message is a conflict.
Only a successful public State CAS can reserve the message durably.

`register_command` prepares a *separate* journal value. It preserves the full
signed canonical string, command ID and SHA-256; the same key with different
bytes is a conflict. The v1 profile uses the SDK's `task://<UUIDv7>` command-ID
form. It requires a signed representation, controller/Realm match, no global
meta revision guard, the original input for submit, and transcript-specific
expected revision/CAS for writeback. It does not verify signatures or grants;
Root performs those checks when the exact command is executed.

The future coordinator must persist the pending transcript before journaling
submit, confirm journal persistence before dispatch, and replay the original
command after receipt loss. Persisting the journal must not change the target
transcript's expected revision. Task terminal observation and transcript
writeback remain two transactions. UNKNOWN effects or a lost receipt must not
produce a new Task or model dispatch. Unrelated transcript CAS conflicts stop
coordination; there is no automatic merge.

Journal-write response loss is resolved by an audited read and comparison of
the original message/stage/hash. No recursive journal is created for a journal
write. Missing entries may only be retried against the same observed revision.
Signatures/nonces remain in the controller-protected journal; private keys and
bearer credentials are never journaled.

Root's mandatory State redaction also applies to command strings. A valid
nonce that resembles a key can therefore change during persistence. Recovery
must validate the stored canonical bytes against the original journal hash
and stop on any change; it must never re-sign, regenerate the command or bypass
redaction. A native canary test covers this boundary. The future coordinator
must perform this read-back validation before executing a journaled command.

## Context, summaries and migrations

`completed_context` allowlists committed messages, policy, summary and session
identity. It excludes pending, journal State IDs, commands, signatures and
controller metadata. The current input is supplied separately, once. This is
document preparation, not a claim that Host has projected the session.

Summary provenance includes the exact covered committed message prefix,
content/renderer/tokenizer/redaction Artifact IDs and the source transcript
revision. Pure checks establish reference consistency; the future controller
must verify source revision membership and actual Artifact bytes/authority.

The current public Context profile freezes State revision bindings but does
not capture their transcript content. S06 needs a versioned, authoritative
Context source/renderer contract to consume only committed history/summary
and keep control State out of model Projection. Copying transcript text into
the current Task input would bypass that boundary and is not implemented.

Migration policy is identical-schema-only. Upgrades must retain v1 schema and
both bindings, or use an explicitly reviewed migration and normal Composition
transition. Experiment sessions require fresh cloned State IDs; production
IDs cannot be reused. There is no implicit migration, branch, merge or
multi-session routing.

## Evidence and remaining work

`test_session_documents.py` covers deterministic document checks, retry/input
conflicts, exact command retention, separate journal targets, summary sources
and Context allowlisting. `test_session_document_state.py` installs an
independent signed package and verifies both frozen schemas using real public
State commands, unchanged signed journal bytes, independent transcript CAS and
exact replay. It never dispatches a Task or reads private storage.
The redaction canary separately proves that changed command bytes are refused
before recovery can execute a command.

`agent_meta_seed_harness/session_coordinator.py` now implements the plan's
message protocol as a consumer-side coordinator over public SDK State CAS and
exact signed commands:
reserve pending before dispatch, journal the signed bytes before Task.Submit,
write the receipt back, wait for the committed terminal, register the writeback
journal entry, then append the message once and clear pending. It never
regenerates a command identity. `test_session_consistency.py` drives this
coordinator against a real daemon with real Tasks and proves, per message:
identical retry recovers the original operation without a new Task, a different
input for the same message identity is a conflict, concurrent admission while a
message is pending is refused, journal registration does not move the
transcript CAS and the exact signed bytes plus SHA-256 are retained and replay
idempotently, the model projection's `task_input` body is exactly the current
input with no pending/journal/signature control fields, an external transcript
CAS conflict stops the round with no merge, append or redispatch (and the
diverged journal then fails closed), summary provenance commits against real
committed history at a real source revision, and both rounds' Tasks run under
one frozen serving revision/composition. Terminal status is taken from
Task.Wait only; the pending item never carries terminal fields.

`test_session_recovery.py` (SH-SESS-02) kills the owned daemon at each named
protocol boundary and restarts a fresh coordinator that recovers from
committed State only: pending persisted before submit (journal still empty,
dispatch then happens once), an ambiguous journal write (recovered by reading
the registered message/stage entry and replaying those exact bytes), an
accepted Task whose submit receipt was lost (the original command replays to
the same Task identity; the fresh incarnation never submits), a terminal
observed before writeback (re-waiting returns the committed terminal without
a model call), and a committed writeback whose response was lost (exactly one
message stays appended and the writeback command replays idempotently). Each
scenario counts real model dispatches through Provider probe events across
daemon generations and asserts exactly one Task, one append and no
redispatch. Declared failed and cancelled terminals are recorded with a null
result reference and never resubmitted, and a Seed package upgrade preserves
both session States while the next message runs under the new serving
composition.

Input redaction receipts, frozen Context integration of committed history and
summaries (the model input still carries only the current message) and
release evidence remain required. Passing recovery tests does not close
SH-SESS-01/02's release evidence, RP-05 or the session profile.

`agent_meta_seed_harness/repl.py` is the plan's minimal interactive front-end
and diagnostics layer (steps 4/5). `next_message_id` proposes stable,
deterministic message identities from the observed document. A REPL attach
recovers any pending round before new admission: an unjournaled pending
message is submitted as a new durable identity, journaled bytes are replayed
exactly, and an observed receipt only waits for the terminal. Each free-text
line then drives one complete durable round through the coordinator; there is
no new protocol surface. `/history` lists committed and pending rounds and
`/explain <message_id>` explains any round from public records only: the
committed or pending fields, the journal's stage entries with command
identities and hashes and, for committed rounds, the public Task trace's
composition and action count. Unknown messages and malformed traces fail
closed. `tests/contract/test_session_repl.py` proves stable identity
determinism, two scripted rounds with `/history` and `/explain`, and attach
recovery of an interrupted round (exactly one model call per round across the
restart, journal stages SUBMIT/WRITEBACK per message) against a real daemon.
