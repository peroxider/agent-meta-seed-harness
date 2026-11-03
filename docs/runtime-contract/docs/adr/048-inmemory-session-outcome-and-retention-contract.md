# ADR 048: InMemory session, outcome and retention enforcement

Date: 2026-10-31
Status: accepted for implementation; real Host assembly remains OPEN

## Decision

Harden the existing InMemory Backend before using it for AC-M17. A request must
use an actually negotiated session owned by this backend instance. Restored
contract-test state does not resurrect an old process's session. Handles must
match backend/request identity and incarnation. Closing a session refuses new
submissions while preserving advisory reads/cancellation/ack of existing work.

Submit replay must retain Realm, operation, idempotency/reversibility, payload,
deadline and retention semantics; only the transport session/authorization can
be renewed. A request ID cannot be independently reused under another scope:
the frozen Ack RPC addresses request_id alone. Reconcile is Realm-filtered and
uses handle/payload identity instead of choosing the first ambiguous request.
Acknowledgements require the exact result hash and preserve the first retention
deadline on replay. Conflicting terminal commits are refused without replacing
the first result. Error diagnostics do not include arbitrary exception reprs.

The executor port now accepts a typed ExecutionOutcome carrying an actual
result ArtifactId, normalized usage or an error. Legacy tuple executors remain
valid for existing contract fixtures. Terminal metadata is bounded to 64 KiB;
native Provider objects and serialized authorization are never retained in the
request record. An injected authorization verifier runs before every admission
or replay. An instance without one explicitly reports
UNAUTHORIZED_CONTRACT_TEST_ONLY and cannot establish a product Host claim.

Requests are bounded to 16 MiB. Default retention is limited to 4,096 requests
and a 64 MiB serialized-request-plus-terminal-reserve budget. Capacity exhaustion
refuses new work without evicting an unacknowledged or unexpired request. Only
acknowledged records past their retained deadline can be pruned. These logical
limits do not advertise hard_memory_quota; persistence remains EMULATED.

Cancellation validates its mode and bounds cooperative waiting by the supplied
deadline and a five-second cap. A callback that ignores cancellation yields
UNKNOWN, not a fabricated confirmed terminal; later cancel cannot erase that
uncertainty and a late owner cannot commit a new result. This is cooperative
Python scheduling, not preemption of a callback blocking the event loop.

## Proof and remaining work

Runtime contract tests negotiate real sessions and exercise successful Artifact
results, verification-before-callback, changed semantics, foreign/forged handles,
replay/retention, cancellation suppression and late commit. DurableFakeBackendState
is confined to Runtime contract tests and is not a Seed release proof.

No Host backend selector, bootstrap certificate, persisted binding/ack outbox,
public backend evidence or AC-M17 claim is supplied by this adapter change.
Actual Host/Service-token assembly and independent installed-wheel proofs remain
required. No frozen protobuf field or permission registry entry changes.
