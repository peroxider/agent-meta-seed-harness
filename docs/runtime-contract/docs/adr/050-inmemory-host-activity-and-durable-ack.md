# ADR 050: Actual InMemory Host activity and durable acknowledgement

Date: 2026-10-31
Status: accepted for implementation; public-wheel AC-M17/release proofs OPEN

## Decision

An explicit execution.host_backend=in_memory configuration (or matching start
CLI flag) selects a real InMemory Backend session for Host model/PURE-tool
activity. The existing trusted_in_process profile remains explicit/default;
failure of the selected InMemory trust/session path never falls back to it.
The profile hash freezes the choice, exact features, root-certified Service
token enforcement and durable terminal-ack semantics at Task admission. The
underlying Backend PORTABLE protocol profile is not an OS isolation claim:
persistence is EMULATED and isolation/credentials/network/hard quota unsupported.

The same Actor and installation-scoped Service checks and budget reservations
precede submit. A fresh bounded Service-signed token is verified against the
actual negotiated session, frozen operation/target and exact registered request
before the Backend can schedule its callback. Native package values are
normalized/schema-validated inside that activity; only bytes, usage, stable
error and an actual staged Artifact identity cross the result edge. Tokens are
cleared after enforcement and only public audit hashes/IDs enter Meta Store.

The actual handle is registered in execution_bindings, linked to the Invocation
and real Capability instance through existing execution Facts/causal edges.
Backend terminal observation, normalized Invocation terminal/Artifact and a
BACKEND_TERMINAL_ACK outbox intent commit in one transaction. The dispatcher
performs the hash-checked ack outside the transaction and records observation.
An ack failure is retried from durable intent; a lost ephemeral session is
explicitly recorded as unavailable, never falsely acknowledged or re-executed.
Confirmed normalized results replay from Meta Store. Incomplete outcomes after
owner loss remain UNKNOWN/FAILED_RECOVERY; production does not inject restored
DurableFakeBackendState. All external awaits remain outside writer transactions.

Public API 1.6 adds optional execution_binding metadata to Task.GetExecution
and selected backend/profile metadata to the administrative View. Only
backend/request/handle hashes, public certificate/token audit IDs and ack state
are exposed; opaque handles, signer/keys, token bytes and native objects remain
private. Existing protobuf fields/resource schema one remain compatible.

## Proof requirements

Runtime tests must observe actual negotiate/submit/await/cancel/ack and persisted
handles, enforce wrong tokens/authority, and cover lost acknowledgement and
confirmed/UNKNOWN restart. Independent AC-M17 must install its own package and
fake Provider/echo under the selected profile, inspect real state/causal evidence
and complete through public APIs. No adapter-only test or healthy flag closes
the complete dependency/release/platform gates or later S04–S07 scope.
