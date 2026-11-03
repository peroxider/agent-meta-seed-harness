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

The required `test_session_consistency.py` and `test_session_recovery.py` gates
remain absent. Task/receipt/writeback crash recovery, input redaction receipts,
frozen Context integration, summary replay, cancellation/failure/UNKNOWN,
upgrade preservation and release evidence remain required. Passing document
preparation tests does not close SH-SESS-01/02, RP-05 or the session profile.
