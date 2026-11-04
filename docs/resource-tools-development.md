# S05 resource adapter development

The Artifact/State adapters use public Runtime execution SPI 1.11 plans and
receipts only. They have no storage, Root authority, native handle, HTTP or
filesystem access. Artifact publication uses the fixed `seed_content` kind;
State writes always supply the expected revision and a content Artifact.
Runtime owns redaction, authorization, frozen revisions/own overlays, CAS,
publication, provenance and the atomic Invocation terminal.

The explicit `tools` package profile includes four Meta resource operations,
six Scratch plans and `seed.transform.normalize_json`, alongside the existing echo. Its signed
descriptors freeze schemas, effects, idempotency and resource contracts. Grants
target the exact tool Capability, State owner or `seed_content` Artifact kind;
there is no REALM_ALL Service grant. Minimal packages retain their original
source allowlist. A separate Provider tools binding uses the same tool maps.
A daemon-level determinism proof submits two identical `normalize_json` calls
inside one frozen Task: both commit the same content-addressed output
ArtifactId with byte-identical normalized bodies, while an altered payload
commits a distinct ArtifactId — the deterministic-tool exit gate, not only an
offline unit property.

The earlier locked API 1.12 input adds ordinary callback schema/redaction/schema
enforcement before journaling/callback entry and output publication. Invalid
encoding, duplicate fields, non-finite numbers, schema failures and expansion
past 1 MiB fail closed. Fatal validation stays fatal on replay even under a Loop
policy that permits ordinary tool errors. Its selected Runtime suite has 1,251
passes and its installed Windows/Linux focused cohorts have 70 passes each;
the preceding public State cohort has 1,231 and 119/119 respectively.
The independent Seed State consumer uses only the installed public SDK and
native CLI. Its recovery fixture discards a committed write response at the
consumer Transport boundary and kills the owned daemon before replaying the
exact signed command after restart. This covers post-commit response loss;
in-commit crashes and expired uncommitted commands need separate proofs.
Independent native consumer fixtures exercise serial typed calls, Artifact
publication/read, frozen State reads, own committed overlays, CAS conflicts,
Actor/Service denial, protected transcript denial (both `seed.state.read` and
`seed.state.write` on a `SESSION_TRANSCRIPT` State are refused
`AUTHORITY_DENIED` with the guarded CAS unchanged), normalization/redaction,
invalid normalizer rollback, inert free text and budget refusal. A confirmed
State resource tool is followed by an actual owned daemon kill; recovery must
reuse its Invocation/output and leave the State CAS at two. A controlled TEST
loopback Messages Provider dispatches `seed.artifact.put` and receives the
public receipt in its next request. Scratch receipts mark oversized output
channels explicitly (`stdout_truncated` with `stderr_truncated`/
`display_truncated` untouched on the same cell), the staged stream Artifact
stays inside the 1 MiB channel ceiling with the small sibling cell untruncated,
and both execution receipts keep their full `scratch-execution-receipt/v1`
shape. This is synthetic evidence with no live
gateway calls, real pricing or captured upstream R2 claim.

The offline tools Provider also bounds normalized history to 4 MiB before
parsing and aggregate tool result content to 1 MiB. Both complete ModelResponse
and terminal-result encodings, including wrappers/escaping, must fit 1 MiB.
Several individually valid large reads therefore fail with RESOURCE_EXHAUSTED
at terminal aggregation; confirmed tool Invocations remain available and are
not repeated or silently truncated.

The full consumer runner accepts independently prebuilt minimal and tools
bundles, both signed outside the consumer run without exporting private keys.
Explicit fault/source variants are separately signed fixture packages. Prior
303-test snapshots retain their API 1.10 input identities.

The current pinned Runtime cohort gives ordinary callback tools distinct child
Actions too. The initiating Actor, Realm, Task, Composition, exact operation
and parent are checked before InMemory token issuance and again when its
verified Action binding is committed. A Task-root token cannot authorize the
tool child. Native consumers cover both trusted and InMemory profiles, including
an owned process kill after confirmation and a callback marker that must not
reappear after recovery. Resource tools keep their existing child semantics.

The current development pin is API 1.15. `capabilities/scratch.py` imports only
public immutable Host plans and returns the Root JSON receipt unchanged, so it
adds no serialization envelope beyond the Host's 1 MiB ceiling. The descriptors
declare six exact resource contracts, per-operation permissions/effects and
bounded input schemas. Output schemas require the versioned Root receipt and
session identity, leaving the resource contract to govern its dynamic fields.
The Service requests exact `capability://seed.scratch` permissions and selected
Artifact-kind scopes, never Realm-wide authority. The optional `scratch` Python
extra and the Windows CI hash lock carry the independent kernel stack.

The offline fake Provider's explicit `sequence` scenario emits one typed tool
call per model turn. `{"$result":{"index":0,"path":["session_id"]}}` selects a
field/index from a confirmed earlier result; future, missing or expression-like
paths fail closed. This is a zero-cost development recipe, not another tool
dispatcher. Normal/free-text workloads retain their existing behavior, and
all generated calls still pass frozen Host schemas, grants and step accounting.

The first installed public-only Seed consumer executes create → execute →
bindings → inspect → export → read stdout → release. It verifies actual Source/
Action provenance, secret-field redaction, canonical package bytes/hash,
trusted-candidate gates, causal output edges and released handle rejection.
The runtime's Root/worker tests are separate evidence and never counted as Seed
consumer coverage. Export does not install a package or change serving.

Independent native consumers also cancel an infinite cell over a separate
control connection and safely inspect its entered binding afterwards. An actual
owned daemon kill preserves confirmed Invocations, expires prior weak handles,
permits audited release after restart, and creates an empty new heap. These are
public SDK/CLI proofs with no database or workspace access. The cancellation
fixture explicitly grants the initiating Actor `task.cancel`; the Harness
Service receives no such grant.

Independent public consumers also deactivate a Composition owning an active
Scratch session, require the Root cleanup Fact before READY, and reactivate via
the approved public package path. The fresh retirement-pin consumer passed all
363 cases, including these six native Scratch cases. That proof is frozen at
`reports/scratch-v3-installed/reports/installed-bytes.json`.

S05/RP-04 remain open. Scratch still needs the remaining authority,
source-export/evolution and broader fault/release matrix.
An additional public-only recovery consumer now checks live-Scratch backup
refusal, release/cleanup, public operator backup and installed native
`agent-meta-restore`, followed by preserved Invocation history, quarantined
snapshot operations, expired handles and a fresh empty heap. It reads only the
explicit backup manifest, never private Runtime DB/CAS/keys/workspaces. Runtime
candidate ADR 075 passed 267 installed checks and 39 independent Seed recovery
checks per Windows/Linux profile. These bounded proofs do not close S05.
Production Provider/EffectIntent/Managed integration and
the remaining fault/release matrix also remain open.
