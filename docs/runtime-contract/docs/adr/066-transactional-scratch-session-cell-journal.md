# ADR 066: Transactional Scratch session and cell journal

Status: private Root persistence foundation; public Scratch Host and S05 open.

An owned kernel is an external effect. A SQLite rollback cannot undo its heap
changes. Root therefore records admission, possible dispatch and native outcome
in separate commands. No writer transaction spans worker startup, a cell,
inspection, interruption, shutdown or filesystem cleanup.

The private `adapters/store/scratch_journal.py` mutators run inside the existing
`execute_command` Unit of Work. Session projections use the frozen v1 tables;
cells use versioned `scratch-journal/v1` payloads in the indexed immutable Fact
chain. The Scratch entity/event names are registered in the Fact catalog.
This does not silently modify migration 1, its checksum or `user_version`.
No public command, SDK plan, Host method or API version is added by this ADR.
The existing GC registry already scans exact Artifact references in Fact
payloads, so these cell Source/receipt references remain rooted. Future export
Facts must similarly record the full dependency input closure, not only a
package whose opaque CAS bytes happen to contain other Artifact IDs.

Reservation derives Realm, Actor, Task, Action and frozen Composition from the
actual Invocation rows. A new session records its Epoch, workspace, backend
request and bounded idle/wall lifetime. Its workspace must belong to the admitted
Action, be active and cover the requested lifetime. One unreleased lifetime per
Realm is enforced under `BEGIN IMMEDIATE`, including STARTING, LOST, FAILED and
RELEASING rows. Recovery must close and clean the old owner before replacement.
All writers must use this path; this is not a physical partial unique index and
does not adopt the legacy in-process controller or its noncanonical identities.

Cell reservations bind an immutable Source Artifact, actual Invocation/Action,
monotonic ordinal, timeout and absolute admission deadline. Only one cell may be
pending. Exact replay returns history; a changed source or timeout is a conflict.
An Invocation cannot acquire a second cell or lifetime under another request.
Registered Artifact integrity is checked here; actual authorized Source reads,
canonical bytes, kind/media policy and pre-execution auditing remain Host duties.

Immediately before dispatch, this journal checks the current Task/Action/
Invocation statuses, Task cancellation/deadline, Realm/Actor/Composition/Epoch
scope and session/cell expiry. A second dispatch is rejected. These checks do
not reserve or reauthorize permissions: the future Host must separately check
the exact Actor/Service grant uses before its only submission. In particular,
an idempotently replayed command receipt or a DISPATCHED journal entry must
never be treated as a reusable execution permit.

Known native outcomes are SUCCEEDED, FAILED or INTERRUPTED with an immutable
receipt Artifact reference; UNKNOWN has no invented result. Output normalization
and Invocation completion follow this observation and cannot rewrite it. An
already dispatched outcome may still be recorded after Task failure, deadline
or Epoch rotation, while retaining its original identity binding. Conflicting
terminal observations are rejected. No global Task or Invocation terminal status
is changed by these private mutators.

Owner loss resolves a merely RESERVED cell to NOT_DISPATCHED and a DISPATCHED
cell to UNKNOWN. Both remain historical, non-executable results. The session
becomes LOST and all LIVE binding handles become EXPIRED in the same command.
Restart reads this committed history; it never adopts a kernel, restores a heap
or redispatches an uncertain cell. A lifetime is bounded to 10,000 cells; journal
reads have an explicit three-events-per-cell ceiling.

Release first persists RELEASING. Confirmation requires recovered pending cells
and the workspace's RELEASED projection, then records RELEASED and invalidates
remaining bindings. These are Root bookkeeping conditions, not proof that a
native process stopped or a path was removed. The future owned Host must supply
actual native lifetime and auditable cleanup evidence outside the transaction.
Repeated release/recovery is idempotent and emits no duplicate Scratch Facts.

Tests use actual SQLite commands, immutable identity triggers, Fact chains,
two concurrent writer connections, reopen/recovery and injected post-mutation
failures. One test-owned orchestration additionally executes an actual isolated
kernel and commits a Root Fact on a second connection while the cell is running.
It verifies exact executed-source identity and the subsequent receipt reference;
it is not a public authorization, signed adapter or Seed integration test.

Remaining integration includes Actor/Service grant admission and dispatch tokens,
an async Root-owned Host port, frozen redaction and bounded channel publication,
authoritative binding observations, Source-only candidate publication/GC roots,
native owner/cleanup reconciliation and public installed Seed consumer tests.
S05, RP-04, Managed Host and release gates remain open.
