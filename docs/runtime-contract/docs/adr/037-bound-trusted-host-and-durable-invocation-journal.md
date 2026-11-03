# ADR 037 — Bound trusted Host and durable invocation journal

Status: development implementation; external consumer verification pending.
Date: 2026-10-30. Extends ADR 032/036. No released Host version is claimed.

## Decision

The daemon assembles an installed-package catalog, asynchronous reconciliation,
an asynchronous outbox and a Task executor. Only a verified package whose
publisher was explicitly trusted may use this initial `in_process` placement.
An actual synchronous zero-argument factory creates the adapter. Each slot has
a durable Capability instance, a binding incarnation and a real PURE health
callback. Rebinding after owner restart repeats factory and health observation;
persisted READY refs alone cannot enable Task admission.

The external package owns its Loop. Runtime owns Context registration,
authority, budget reservation, normalized invocation results and Task terminal
commit. Neither an importable adapter nor an installation row establishes
execution support. Failed candidate activation revokes that candidate's scoped
grants atomically, preserving the existing serving installation and grants.

## Frozen acceptance and facade

Task acceptance stages Surface and `task-acceptance-view/v1` bytes in CAS before
the transaction. The accepting transaction recomputes and compares both complete
preimages, including the command's authority use, serving revision, State refs,
package ownership, epoch, authority fingerprint and backend profile. Conflicts
reject admission. The acceptance Fact references the immutable View artifact.

`sdk.host.TaskEnvelope` now includes `composition_content`,
`acceptance_view_artifact_id`, `acceptance_view_content` and
`harness_manifest_content`, alongside input, Surface, State bindings, policy,
budget, deadline and accepted meta revision. Snapshot values are immutable and
the View content must match its ArtifactId. This changes the development DTO
constructor; update consumers and repin the wheel before using these fields.

The facade exposes `project_context`, `invoke_model`, `invoke_tool` and
`check_cancelled`. A model can use only a ContextProjection issued to that
session. Initial Context supports `utf8-bytes/v1`, at most 1 MiB, and frozen
input/Surface/View artifact sources. Counts are verified independently and
include section delimiters; a durable ProjectionManifest records provenance.
This does not implement arbitrary State/Fact reads or the full S02 budget ladder.

Model history is canonical JSON, initially `[]`. Each model item is
`{"role":"model","response":<complete model-response/v1 object>}`. Each tool
item has `role`, `call_id`, `error_code` and `content_hex` (null on error).
The ordered complete normalized model response is preserved. Only the next
normalized ToolCallPart can dispatch; IDs are unique across the Task, tools run
serially, free text cannot dispatch, and terminal bytes must equal the complete
last terminal model response (including LENGTH/truncation).

The supported JSON Schema subset fails closed on unsupported assertions.
Input and output are checked against registered descriptor schemas. Initial
tools are PURE with `none` effects. Model results must explicitly report zero
cost; unknown tokens remain null. Network, credentials, paid providers and
external tool effects require later controlled execution profiles (RP-03/04).
The trusted in-process profile is cooperative, not an isolation boundary or
hard preemption claim.

## Durability and authority

Before calling an adapter, one transaction authorizes both the active initiating
principal and the actual installation-scoped Service grants, reserves uses and
turn/step/model/effect counters, registers canonical request bytes, and records
Invocation DISPATCHED/RUNNING. The daemon bootstrap grant cannot substitute for
a scoped model/tool grant. No database transaction spans an adapter await.

`invocations.backend_ref_json` carries `host-invocation-journal/v1` with
`request_id`, zero-based `ordinal` and `request_hash`. This is a durable journal
key, not a native BackendHandle. Confirmed output/error replays only when the
ordinal and exact request bytes match, without redispatch or another debit.
After restart, incomplete dispatched invocation outcomes fail recovery with
EXTERNAL_EFFECT_UNKNOWN. They are never automatically retried. Cancellation or
timeout preserves consumed counts and records unknown outcomes explicitly;
Task terminal transitions remain irreversible. Owner shutdown leaves unfinished
work recoverable and unloads package modules after execution tasks are drained.

## Current evidence and remaining gates

Runtime `test_bound_harness.py` exercises real signed AMPAK loading, health,
Task execution, full terminal content, scoped grant exhaustion, budget denial,
cancel/deadline, unknown recovery and confirmed-result replay over public IPC.
These Runtime-owned tests do not close Seed RP-00–RP-02. Independent installed
wheel tests, actual process kill/recovery, upgrade failure preservation, the full
S01A/S02 matrix, package import audit and stronger Backend profiles remain
required. S04–S07 remain in scope and unverified.
