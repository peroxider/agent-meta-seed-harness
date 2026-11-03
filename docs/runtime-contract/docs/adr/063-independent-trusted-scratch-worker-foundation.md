# ADR 063: Independent trusted Scratch worker foundation

Status: private process foundation verified in development; public Scratch Host admission and
S05/RP-04 remain open. Public API stays 1.12 and no Scratch capability is exposed.

The old in-process Scratch adapter cannot establish the independent worker
required by §41.54. A separate fixed Runtime entrypoint now starts IPKernelApp
in a fresh, owner-only workspace with isolated Python, no user site, disabled
SQLite history, a zero output cache and a fixed profile without startup code,
extensions or configuration loading. Only time, timeit and whos line magics
remain. Provider credentials and the caller's general environment are excluded.
This is explicitly trusted exploration, without an adversarial filesystem,
network, memory or execution sandbox.

Jupyter client 8.10 and ipykernel 7.4 are the minimum optional versions because
this implementation requires their CurveZMQ transport support. The owner-only
connection file contains a random HMAC key and Curve keypair; there is no
plaintext fallback. An authenticated readiness exchange and fixed pre-user
probe verify the actual process, isolated profile and native ownership before
the worker becomes active. Readiness accepts only replies to requests issued
by that startup attempt, including an earlier reply after a cold start.

Windows workers join an owner-only KILL_ON_JOB_CLOSE Job before kernel startup,
including the actual Python process behind a venv redirector. Their fixed
control hook delivers a cooperative main-thread KeyboardInterrupt. On Linux a
fixed supervisor owns the process group and arms parent-death cleanup before
starting a kernel; a pidfd retains its original process identity. The supervisor
contains no caller code. This process group does not claim Managed isolation or
containment of hostile descendants that deliberately escape it.

Cells are serial and receive a source-order ordinal. The actual kernel execution
count is preserved separately; disabled history does not imply a nonzero kernel
count. Idle and wall lifetimes cannot exceed 30 minutes and four hours. An
owner-side watcher expires the kernel even if no further request arrives; busy
cells remain subject to the wall ceiling. Entering release rejects new cells.
A fresh worker never restores a previous live heap. Missing terminal confirmation after
worker death produces EXTERNAL_EFFECT_UNKNOWN and cannot automatically retry.

The producer bounds stdout, stderr and canonical MIME snapshots independently
to 1 MiB before Jupyter publication, and the receiver repeats those bounds.
Truncation flags are explicit. Display metadata and live update IDs are removed,
and only bounded builtin JSON values and six MIME types cross the channel.
Exception messages/tracebacks and editor payloads are removed before transport;
only a bounded exception type remains. General live Python values are not sent.

Cancellation first requests an interrupt and waits at most five seconds, then
closes the native process owner. Unconfirmed or forced interruption loses the
session. Explicit release confirms the matching shutdown reply and then closes
the native owner regardless of ipykernel's remaining atexit/thread joins. Native
process termination is observed through retained identities. A known interrupted
cell can leave the same kernel usable; a lost worker cannot execute another cell.

Runtime-owned tests exercise actual kernels, output ceilings, sanitized errors,
expiry/fresh heaps, cooperative interruption, ignored interruption, self-exit,
forced descendant cleanup and abrupt owner death without Python cleanup. Private
installed wheel cohorts and their hashes remain separate from Seed's previously
verified inputs. In-process tests and private worker proofs are not public Host
or release evidence.

Still required: typed public plans and Root admission; exact Actor/Service grants,
Realm uniqueness and durable session/cell/Action/Invocation journal; frozen policy
redaction and output Artifact publication; restart reconciliation and expired weak
handles; bounded safe binding inspection; source-only export with AST dependency
validation; auditable workspace removal; and independent signed Seed consumer
integration. No Scratch descriptor or grant may be advertised before that path
exists and is tested.
