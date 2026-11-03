# ADR 070: Public Source-only Scratch candidate export

Status: API 1.15 candidate verified: 1460 selected Root unit tests and 345 tests
in each fresh Windows/Linux installed environment, including 11 public export
cases. Evidence: `reports/scratch-public-export-v1-input/verification.json`.
Seed publication, S05/RP-04 and complete lifecycle/release gates remain open.

`sdk.host.ScratchExportCandidate` is an immutable intent containing a session,
one to 64 unique Source Artifact IDs, one to 100 selected top-level definition
names, contract and dependency-lock IDs, `scratch_candidate:<selected-name>`
entrypoint, dependency wheel IDs, supporting Artifact IDs and bounded package
name/version. The contract is `scratch.export/v1`, KEYED, effect `artifact.put`,
requiring `scratch.export` and `artifact.put` plus scoped Capability invocation.
The ResourceAdapter uses synchronous planning/normalization callbacks as before.

Root verifies frozen operation, actual Task/child Action and Invocation, current
session owner/Realm/Composition/Epoch and ACTIVE lifetime. Both Actor and Service
need each exact scoped grant, including Artifact-kind access derived from actual
registered input metadata. Restricted or invalid inputs fail closed. A Source
must occur in this session's confirmed immutable cell journal; no live binding,
foreign session Source, filesystem path or heap serialization is accepted.
For bounded Root provenance, each selected Source records its latest confirmed
cell Action/Invocation and occurrence count. All historical cells remain Facts.
Source order remains explicit and semantic in the pure constructor.

Each Source/contract/lock/support document is at most 1 MiB; each wheel at most
32 MiB; the whole authorized input set at most 72 MiB. The constructor additionally
enforces 4 MiB aggregate Source and 64 MiB aggregate wheel limits, AST/compiler
scope checks and the locked module/wheel profile from ADR 065. Root retrieves
hash-verified immutable bytes outside a writer. Contract and transitive JSON
Artifact references require an exact explicit support closure (bounded to 256
IDs); missing or extra support references are refused. Source/contract/lock
requiring frozen policy redaction are rejected instead of altering canonical
code or identity. Opaque wheel bytes are authorized build inputs, not values
from the kernel or a promise of binary content redaction.

The pure constructor runs off the daemon event loop on frozen input bytes. It
imports/installs/executes no candidate or wheel. Cancellation may leave that
bounded pure computation finishing in its thread; it cannot mutate Root/CAS or
publish anything. No writer spans construction. This operation has no native
dispatch, so it uses Root resource publication authority rather than minting a
kernel Service token or widening native execution certificates.

Preparation stages package/provenance/receipt bytes without registering them.
After normalizer schema/policy checks, Root revalidates the exact reserved grants,
session and input metadata in the terminal writer. Package and build provenance
registration, used/produced causal edges, `scratch_candidate_exported` Fact and
successful resource Invocation commit atomically. The Fact explicitly retains
every input ID for GC; opaque package bytes alone are not a retention root.
Failed normalization or commit publishes no candidate. Confirmed replay uses
the immutable resource terminal record and skips callbacks/build/publication.

The bounded receipt returns package/provenance/input IDs, Root source origins,
actual exporting Action, `trusted_candidate`, `serving_changed=false` and
`experiment_promotion_required=true`. It never returns a live object or claims
that World/Experiment/Promotion has passed. Export does not install or promote
the package. Further consumer, World-build and evolution gates remain required.

Runtime-owned signed public-package tests cover identical constructor/package
bytes, original-cell-only execution, Source/Action origin, GC roots, closure and
hidden-global rejection, Source membership, actual Artifact-kind scope, policy
refusal, failed normalization, revoked reserved authority and confirmed replay.
They do not substitute for installed independent Seed consumer evidence.
