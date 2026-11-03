# ADR 035: Local daemon ownership, discovery and incarnation-bound stop

Date: 2026-10-30
Status: implemented control-plane slice; bound execution/recovery gates OPEN

## Decision

Add the Public API **1.1** method `agent_meta.public.v1.Runtime.Stop`, using the
existing CommandRequest and MutationResponse messages. No protobuf field number
changes. Its registered payload is `runtime.stop/v1` with exactly
`instance_id,reason_code`; it requires the frozen `runtime.admin.stop`
permission. Existing methods remain available to clients negotiating API 1.0.
The new method is refused on a connection that negotiated minor 0.

The existing Hello response's `server_instance_id` becomes the authoritative
connection identity. Public `LocalTransport` and `AgentMetaClient` expose it;
`stop_runtime` binds its signed command to that exact incarnation. A fresh
command targeting another incarnation is refused. Authenticated committed replay
returns the original receipt/resource, including after restart, but never stops
the replacement incarnation. `STOPPING` acknowledges durable admission and does
not assert that the OS process has already exited.

The server notifies its owner only after a successful response has been written
and drained. Failed authentication, malformed payload or failed writes cannot
signal shutdown. If a caller loses the response before notification it can
replay the same command and recover the receipt without another stopping Fact.

`agent-meta --data-dir PATH start` runs in the foreground. It requires completed
bootstrap, acquires the actual OS writer lock, verifies credentials against
committed identities, loads/redacts configuration and runs the full integrity
doctor before exposing the local endpoint. It records `runtime_started` under
the real Service identity. Discovery derives the endpoint from the canonical
data directory, authenticates the OS peer and negotiates Hello; reading a stale
PID file is never ownership evidence. `info` includes the authenticated instance
ID. `stop` signs through Runtime's scoped operator credential adapter.

Repeated init now also holds the same writer lock while verifying/cleaning
bootstrap. A concurrent start/init refuses with ALREADY_RUNNING / exit 12.
Windows lock metadata records the process creation FILETIME to distinguish PID
incarnations. Run-directory/lock reparse points are rejected.

Shutdown closes the local server/connections, records local signal shutdown when
needed, checkpoints WAL, closes the store and releases the OS lock. Abrupt
process death relies on OS lock release and durable SQLite state, not PID-file
deletion. Each successful owner has a fresh random instance ID. Start failures
release all resources they acquired. Startup exit codes follow §41.39.2.

Root readiness must refer to the active Epoch's actual Root Principal/Grant;
an unrelated active Service Grant cannot keep Root readiness green after Root
revocation.

## Current execution boundary

This slice assembles the real **control plane**. It does not yet attach the
Task Host, scheduler, Backend session, reconcile delivery or invocation recovery.
Consequently it always refuses execution readiness, including when persisted
refs claim a serving revision. There is no fake slot executor, fabricated Task
handle or silent in-process fallback. Empty bootstrap remains core-ready and
serving-not-ready, with the actual readiness evaluator.

The future bound Host must add its ingress stop, running-task grace/cancellation,
dispatcher/reconciler drain, terminal flush and Backend-session close ahead of
the final WAL checkpoint. It must re-establish serving health after restart.
AMPAK factory/health lifecycle must also be callable without manufacturing a
Task solely for a probe. Durable known-result replay/UNKNOWN handling and the
independent package lifecycle remain prerequisites for RP-00–RP-02 closure.

## Evidence

- `tests/unit/test_daemon_lifecycle.py`: real lock/store/local transport, signed
  stop, unsigned/wrong-incarnation rejection, replay after replacement, Root
  revocation readiness and API 1.0/1.1 negotiation.
- `tests/unit/test_daemon_process.py`: published console entry point in separate
  isolated Python processes, duplicate owner/init exit 12, signed clean stop,
  forced process death/restart and failed-start cleanup.
- Existing bootstrap, local-server, SDK/CLI and lock regressions remain required.

Runtime does not consume external Seed results as its own release input. Seed
must pin the actual wheel/contract hashes and independently exercise these
published entry points before recording consumer evidence. A working daemon
alone does not establish a working Harness Host or a releasable Seed profile.
