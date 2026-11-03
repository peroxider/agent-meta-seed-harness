# ADR 031: Public Harness consumer contract

Date: 2026-10-30
Status: accepted for implementation; release gates remain open

## Problem

The Seed consumer cannot build an AMPAK or bind a running Task using public
imports. ValidatePackage currently checks only the outer manifest, allowing
invalid signatures, missing content and incompatible packages to appear valid.
Private store calls and Runtime test fixtures are not an acceptable consumer API.

## Decision

Deliver the missing interfaces in independently testable increments. First,
publish `agent_meta_runtime.sdk.packages` as the supported AMPAK construction
and manifest signing-preimage API. These are offline, pure functions; they
confer no Authority. Existing package bytes and manifest fields do not change.

Harness Contract 1.1.0 specifies publisher identity content as exactly 32 raw
Ed25519 public-key bytes and signature content as exactly 64 raw signature
bytes. Their ArtifactIds hash those bytes. Signature verification covers the
existing domain-separated manifest preimage. A valid publisher signature proves
provenance, not publisher trust, execution placement or permission to activate.

ValidatePackage must read and hash-verify every referenced artifact, decode
AMPAK without extraction/import/execution, check package identity, all three
version ranges, loop policy, grants and supported placement/features. Unknown
or unavailable dependencies fail closed. Install and Activate rerun validation.
The validation plan hash binds all verified input ArtifactIds and resolved
contract/backend versions; it never includes wall time or local paths.

Do not claim RP-00, RP-01 or RP-02 closed until a separately installed consumer
wheel proves loading, execution and durable recovery through a public Host.
Host SPI, platform transport, credential enforcement and State/Evolution
extensions require their own explicit contract increments and proofs.

The public SDK also exposes `connect(data_dir)` and `LocalTransport` using the
existing Public API v1 framing over UDS/Windows Named Pipe. Windows checks the
peer process TokenUser SID on both endpoints before Hello; it never falls back
to TCP. RPC deadlines are absolute UTC microseconds; Wait uses its own bounded
deadline with transport grace for a nonterminal response. Cancelling a request
closes the sequential channel so a late frame cannot answer a later request.

Windows CAS publication uses MoveFileExW with MOVEFILE_WRITE_THROUGH after the
staged file is flushed, because POSIX directory fsync is unavailable there.
These platform corrections do not certify the complete daemon/Host lifecycle.

## Consequences

Malformed packages formerly accepted by structural validation are rejected.
Existing offline AMPAK/manifest helpers remain byte compatible. Seed uses only
public symbols. Runtime retains zero dependency on Seed. No product release or
external Seed gate becomes VERIFIED merely because these helpers exist.
