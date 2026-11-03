# ADR 047: Root-certified Service execution authorization

Date: 2026-10-31
Status: accepted for implementation; Backend/Host integration remains OPEN

## Decision

Implement the existing §41.41 execution-token contract before attaching real
Backend activity to the public Host. This is not an alternate nonce or unsigned
in-process authorization shortcut. A worker pins the Root identity/public key,
Realm and Epoch independently, validates a Root-signed public Service certificate,
and checks every token using that distinct Service Ed25519 key. Crypto/signing
are injected into the pure domain validator; private keys never enter its state.

The certificate envelope is `{schema,root_principal_id,certificate,signature}`,
with schema `service-execution-certificate/v1`. Its certificate has exactly the
specified `service_principal_id,public_key,realm_id,epoch_id,permissions,not_after`
fields; public_key and signature use lowercase raw-byte hex. Root signature
preimage is `agent-meta-service-certificate-v1\0` plus JCS certificate bytes.
Certificate permissions bound token issuance; they are not a substitute for the
Actor/Service Grant checks and reservations that must precede each effect.

The token envelope is `{payload,service_principal_id,signature}`. Its payload
retains the exact twelve frozen fields and signature preimage
`agent-meta-execution-token-v1\0` plus JCS bytes. token_id is a canonical UUIDv7;
times are Unix microseconds. TTL is positive and at most sixty seconds; expiry
must fit the certificate and Task deadline. The worker's independently derived
binding fixes session/Realm/Epoch/actor/Action/effect/target hash, required
permissions and finite resource ceilings. No scalar coercion or unbounded
ceiling is accepted. Current permission/effect registries are unchanged.

The bounded worker nonce cache allows exact token/request/payload replay only,
refuses token or nonce reuse for another request, and rejects new tokens at
capacity instead of evicting unexpired replay protection. Expired entries can
be pruned because expired tokens fail time checks first. All failure diagnostics
use fixed reason codes; returned audit data contains only token_id, payload hash,
Service public-key ID, public certificate ArtifactId and request/expiry metadata.
Serialized tokens are enforcement-only, never stored as Artifacts/Facts.

## Remaining integration and proof

Real-signature domain tests must cover chain substitution, distinct keys,
malformed canonical encodings, every binding/ceiling/time dimension and replay
capacity. This foundation alone does not create bootstrap certificate records,
attach a worker, implement durable terminal acknowledgements or satisfy AC-M17.
Those require actual Backend session/submit/handle/await/cancel/ack assembly,
public installed-wheel evidence, and separate truthful feature declarations.
