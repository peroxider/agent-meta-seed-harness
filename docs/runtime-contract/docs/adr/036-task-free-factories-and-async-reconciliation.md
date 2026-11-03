# ADR 036: Task-free factories and asynchronous reconciliation

Date: 2026-10-30
Status: implemented prerequisites; bound Host/consumer recovery still OPEN

## Host lifecycle contract under implementation

Refine ADR 032's unadvertised execution SPI: the synchronous AMPAK entrypoint is
`() -> HarnessAdapter`. It receives no fabricated TaskEnvelope, Runtime facade,
credential or repository. Real accepted Tasks enter only through
`run_task(TaskEnvelope, TaskRuntime)` and the typed Model/Capability invocations.
An async factory is rejected without awaiting it. Factory errors, including a
package-raised StableError, are normalized without retaining their raw message
or details. Operator trust and in-process placement are checked before import.

HarnessAdapter now also requires an asynchronous, PURE
`probe(HealthProbeInvocation) -> HealthStatus` callback. The task-free request
contains the stable request ID, actual slot/Capability/descriptor/operation
identity and deadline. HealthStatus is exactly READY/DEGRADED/UNHEALTHY with a
bounded uppercase stable reason token. Runtime owns timestamps, retry attempts,
gate decisions and Facts. A required probe is not satisfied by the mere presence
of callable Python objects. Factory/probe code must not perform State, network,
credential or external effects.

This corrects factory/health lifecycle preparation; it does not advertise Host
SPI support yet. Harness Contract remains 1.1.0. Contract 1.2.0 / Host SPI 1.0.0
must wait for real daemon/Backend/Task/recovery and independent consumer proof.

## One semantic reconcile program

Reconciler's existing A–H transactions now form one internal generator program.
Synchronous and asynchronous drivers execute the same phases; there is no
second cutover algorithm. Only instantiation, probing, retry sleep and drain
suspend as external calls. Before each external call the owner verifies that
its SQLite connection has no open transaction. One Reconciler instance accepts
one round at a time across both entry points.

`ProbeRunner.run_async` uses the same normalization, stable request identity,
required/optional gate and 1s/2s retry ladder as `run`. It applies cooperative
deadlines and rejects a late READY result, including one returned after a
callback suppresses deadline cancellation. Cancellation propagates rather than
being reported as success. This is not a hard-preemption claim for arbitrary
trusted Python code; required stronger isolation still needs its Backend.

Async suspension makes concurrent desired transitions observable. Every cutover,
failure mark and realized completion is guarded by the captured desired
revision/CAS. A superseded round cannot move serving or mark the replacement
cycle READY/FAILED. This also applies while draining to the revision-0 sentinel.
Realized CAS uses the original snapshot, never a newly read CAS that could
authorize overwriting another round's progress. External error text is not
copied into reconcile Facts or results.

## Evidence and remaining assembly

`tests/unit/test_async_reconciliation.py` verifies actual coroutine suspension
outside transactions, owner serialization, supersession before cutover/after
cutover/while draining to zero, cancellation, retry identity, late READY rejection
and error-canary omission. Existing synchronous Reconciler/Probe/lifecycle and
state migration tests continue to run against the same program.

`tests/unit/test_harness_package_loader.py` verifies task-free factories,
typed probing, artifact-specific imports and normalized failure behavior. These
are Runtime service tests with injected external transports; they do not prove
an executing installed Harness. The daemon remains execution-not-ready until a
real Host owns instances, health, scheduling, budget/Authority, invocation and
terminal persistence and recovery. RP-00–RP-02 remain OPEN.
