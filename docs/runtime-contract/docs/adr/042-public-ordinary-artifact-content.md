# ADR 042: Public ordinary Artifact content reads

Date: 2026-10-30
Status: accepted for implementation; RP-04 and external release gates remain OPEN

## Decision

Public API 1.3 adds `agent_meta.public.v1.Artifact.GetContent` with the existing
`GetArtifactRequest` and `ResourceResponse` protobuf messages. It returns the new
schema-version-one `artifact-content/v1` resource: `artifact_id`, `kind`,
`media_type`, `size_bytes`, `content_hex`, `resource_type`, `schema_version`.
The SDK exposes `get_artifact_content(artifact_id) -> bytes`; CLI
`artifact content <artifact-id>` returns this data as ordinary JSON/hex output.
Existing manifest/verify methods and protobuf field numbers are unchanged.
Negotiated minors below three refuse the new method before dispatch.

This is a normal-content read behind the same-owner authenticated operator IPC
boundary, not a Harness credential or filesystem capability. It performs no
mutation, command claim, authority-use reservation or CAS publication. It can
read at most 1 MiB per request. Larger objects return RESOURCE_EXHAUSTED; this
version does not promise streaming/range support. Responses contain no CAS path,
storage manifest, key handle, encryption metadata or Provider-native object.

The service rejects any Artifact with an encryption record or a restricted blob
record, including rotated, deleted and crypto-erased revisions. It never falls
back to a coincidental plaintext copy or treats operator identity as an implicit
`artifact.read.restricted` authorization. Authorized restricted reads/decryption
remain a separate, unimplemented audited interface. This adds no raw-retention
or encrypted-upload support and does not close the whole RP-04 dependency.

For ordinary content, the service verifies identity syntax, registered integrity
status, the size ceiling and storage metadata before reading CAS. The read is
bounded by the declared size plus one byte, then checks exact size and SHA-256.
The SDK independently checks schema version, requested identity, byte count and
content hash. Integrity or I/O errors expose stable codes without storage paths
or raw content in error details. A missing Artifact returns NOT_FOUND.

## Proofs

Runtime tests must exercise real IPC binary/empty/boundary reads, oversized,
missing/corrupt storage, restricted/tombstoned classifications, no plaintext
fallback and old-minor refusal. Consumer tests must use only installed wheels
and the public SDK/CLI, compare bytes with independent expected content and
never open Runtime storage paths. S05 State/Scratch and S04 secure Provider
execution remain separate development work.
