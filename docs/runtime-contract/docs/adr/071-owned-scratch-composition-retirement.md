# ADR 071: Root-owned Scratch retirement during Composition drain

Status: API 1.15 compatible candidate fix verified: 1463 selected Root unit
tests and 348 tests in each fresh Windows/Linux installed profile. Evidence:
`reports/scratch-drain-v1-input/verification.json`. Independent Seed retirement
validation remains pending for this new wheel.

The original public Scratch candidate allowed deactivation to report READY and
release its package binding while a kernel from that Composition remained ACTIVE.
That volatile session then prevented another Realm session and could not be
released by a retired package. A real native regression reproduces the gap;
the failing baseline report is retained.

The installed Harness catalog now invokes a private Root resource retirement
callback after old Tasks finish and before Capability instances/bindings are
released. RuntimeDaemon supplies its owned Scratch coordinator. The coordinator
selects only Root-journaled unreleased sessions of the retiring Composition and
Realm, serializes against that session's operations, persists the cleanup plan,
closes the actual native owner, checks/removes its allocated workspace, expires
handles and confirms RELEASED. Recovered LOST sessions use the existing exclusive
daemon/native-parent ownership contract; no heap is adopted.

This is Core lifecycle authority following an approved serving transition,
not a package-accessible bypass of `scratch.release` grants. Cleanup Facts keep
the original resource/Action lineage and additionally record the retiring
Composition, reconcile ID, requesting Service and `COMPOSITION_RETIRED` cause.
No package callback, writer or credential crosses native shutdown/deletion.
Cancellation awaits the protected cleanup before releasing its owner reference.

A failed drain retains its binding/instances and reports DEGRADED. HostControl
already retries that durable outbox intent with backoff. Because serving has
already moved by then, Reconciler must carry both old serving and old realized
revisions. The catalog retires each distinct nonzero previous generation,
excluding the new serving target. Otherwise retry would see old serving zero
(or equal to the new target) and falsely complete without cleaning the still
unrealized old generation. Later superseding transitions retain both generations
rather than forgetting a prior incomplete drain.

Native tests cover successful cleanup before READY, unavailable cleanup retaining
DEGRADED/binding followed by successful automatic retry, and a genuinely entered
infinite cell: retirement waits for its Task, public cancellation interrupts it,
then retirement closes the owner and workspace. Existing Harness activation,
restart and deactivation regressions run alongside them. Independent Seed
retirement and fresh Windows/Linux wheel proofs remain required for publication.

The Host profile advertises `scratch_retirement=ROOT_OWNED_COMPOSITION_DRAIN_V1`.
No SDK/RPC or resource-plan shape changes, generic isolation upgrade, production
Managed guarantee or complete S05/release claim follows from this fix.
