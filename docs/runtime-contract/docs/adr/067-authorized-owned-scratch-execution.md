# ADR 067: Authorized owned Scratch execution

Status: private Root execution assembly. Public Scratch Host, creation/release
authorization, output publication and Seed consumer integration remain open.

The journal in ADR 066 is historical evidence, not a submission permit. The new
private assembly combines actual Task admission, grant reservations, certified
execution authorization and an owned independent kernel. It is not mounted on
the package facade, exposed from the SDK or included in the public resource
operation registry. The published API/profile and Seed Runtime pin stay unchanged.

`ScratchExecution` is a secretless intent binding a canonical session/Source
Artifact, absolute deadline and a positive execution budget capped at 30 seconds.
Zero is an expired timestamp, never an absent deadline. The private operation
declares KEYED idempotency, `scratch.execute` permission and the conservative
registered `external.irreversible` effect. Trusted code can have external effects;
an ephemeral heap is not evidence that arbitrary Python execution is reversible.

Root resolves the operation from the Task's actual frozen Surface, Composition
slots and immutable descriptor revision. The supplied operation must match them.
Admission checks the real Task/Actor/Realm and session ownership, Composition,
Epoch and lifetime. Ordinary Source metadata must be valid, bounded and supported;
restricted Sources fail closed. Actual Source bytes are not read at this stage.

Capability invocation, declared permissions and Source Artifact-kind access are
resolved independently for both Actor and Harness Service. Service grants must
belong to the activation generation visible at Task acceptance. Claims sharing a
grant consume one grouped use, in the same transaction as child Action,
Invocation, budgets, cell reservation and causal Facts. Admission failure rolls
all these projections and Facts back. It does not refund an already admitted use
when later authorization fails, nor borrow a newer replacement grant.

The Root-owned coordinator reauthorizes those exact reserved uses before reading
and hash-checking the immutable Source. It constructs a certified Service token
for the actual child Action, native owner generation, complete intent hash,
effect, call/execution ceilings, permissions and absolute deadline. Signing keys
and token bytes stay in Root; neither enters the kernel or package facade.

`ScratchWorker.execute` accepts a private synchronous submission hook. It runs
after waiting for the worker lock and checking liveness, before accepting the
cell or scheduling native transport. Root reauthorizes the same grants again,
loads current public execution trust, independently verifies the signed token
binding, and atomically records cell dispatch plus immutable token audit. Token
issuance alone is insufficient. A committed dispatch Fact prevents another
submission even if the mutable journal marker is removed. No writer transaction
spans the worker's lock wait or native execution.

The worker recomputes the absolute deadline at its lock and after admission;
queue time cannot become extra execution time. A pre-submission denial closes
only the matching RESERVED cell as NOT_DISPATCHED, preserving the heap. A
malformed second request cannot abort another request's admitted effect.

Native confirmation is bound to the accepted worker ordinal. Before output
normalization, Root persists a bounded receipt containing execution count,
sanitized error type, truncation flags and channel hashes. A confirmed interrupt
remains INTERRUPTED even if Task cancellation wins the return path. Actual owner
loss with no confirmation becomes UNKNOWN and loses the session/handles. Known
native evidence is independent of later Invocation normalization failure.

The coordinator can bind only a fresh actual worker to a STARTING journal
lifetime, with its reserved workspace. A new coordinator cannot adopt an ACTIVE
session or restore a previous heap. Its close path stops owned native processes
and records loss; this is not the normative release/cleanup implementation.

The private tests use real SQLite transactions, immutable identity triggers,
actual Actor/Service grants (including a one-use grant serving three claims),
Root-certified Ed25519 signatures and real independent kernel processes. They
cover revocation before dispatch and during a lock wait, absolute deadline
expiry, malformed concurrent requests, frozen input/scope substitution, forged
signatures, unavailable ownership, actual process exit and confirmed interrupt.
The fixture directly assembles Root metadata; it is not evidence of public
package validation, SDK consumption or installed Seed execution.

Remaining work includes a typed async Host port and public plans, authorized
creation/inspection/export/release, frozen policy/schema output publication,
authoritative binding metadata, auditable workspace cleanup, startup/backup
reconciliation and cancellation-safe scheduler integration. Raw native results
returned here must remain inside Root. S05/RP-04 and release gates remain open.
