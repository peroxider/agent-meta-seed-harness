# ADR 049: Public execution certificate at bootstrap

Date: 2026-10-31
Status: accepted for implementation; worker/Host assembly remains OPEN

## Decision

Fresh native init now stages a public Root-signed Service execution certificate
and commits its Artifact registration plus reference in runtime_initialized in
the existing bootstrap transaction. Root and Service identities/keys are still
distinct, and the Service Grant's exact eight permissions are unchanged. The
certificate limits signing to model.invoke/capability.invoke, with a one-year
not_after; it does not itself grant effect authority. Actor and installation-
scoped Service Grants must still authorize and reserve every invocation before
any worker token is issued. Later operation families require an explicit
appropriate certificate policy, not an implicit expansion of this one.

The frozen builtin-document set stays unchanged. Its public API version reports
the current 1.5 contract. The certificate is a separate authority_certificate
Artifact, pinned by the initialization Fact and the existing GC mark registry.
CAS staging remains outside the transaction, and failed init's existing cleanup
rules preserve keys if commit outcome is ambiguous. No new schema table or
permission registry entry is introduced.

The public-chain loader pins the current Realm/Epoch Root identity, active
Service identity, Ed25519 key, certificate kind/size/hash/signature and exact
subject. Re-init validates a present certificate's integrity without minting a
new identity or silently renewing it. A worker loader additionally checks
not_after; an expired certificate permits verification/administration but not
execution. Old development stores lacking this new certificate are not silently
certified; an execution loader returns KEY_UNAVAILABLE until explicit setup.

The kernel-only Service signing callback opens only the existing scoped
service.ed25519 handle, validates its committed public key and releases its
zeroed buffer. It never reads the Root private key or exposes a signer through
the Harness facade. Serialized execution tokens remain transient; only the
public certificate is registered as an Artifact.

## Evidence and limits

Real Windows bootstrap/scoped-key tests verify the signed chain, distinct keys,
public GC retention, absence of serialized tokens in CAS/Facts, expiry behavior
and corruption refusal without key rotation. Existing bootstrap/backup/credential
tests remain required. This supplies trust material, not Backend execution,
durable binding/ack outbox or independent AC-M17 evidence. No Host SPI version,
product security matrix or Runtime dependency is promoted by these tests.
