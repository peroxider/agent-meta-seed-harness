# ADR 060: Task-scoped Meta resource plans and atomic tool terminals

Status: implementation in progress; no installed consumer or S05 verification claim.

Public execution SPI 1.11 adds immutable `ArtifactRead`, `ArtifactPut`,
`StateRead`, `StateWrite`, `ResourceReceipt` and synchronous `ResourceAdapter`
through `agent_meta_runtime.sdk.host`. `HarnessAdapter.resource_tools` binds
operation IDs separately from ordinary callbacks; collisions are invalid.
The signed operation declares `resource_contract` with one of the four `/v1`
request schemas. Capability contract 1.1 adds that optional field to the frozen
Surface; other operations preserve their prior shape. No built-in RPC is added.
The semantic effect registry adds `artifact.put`; PURE `state.read` consumes a
tool step without consuming a mutation effect. Publication and State writes
consume one effect each. State writes also require ordinary read authority for
the actual source Artifact kind, in addition to authority over the State owner.

Planning receives immutable Task/call data only. It cannot commit a Fact or
obtain a store, credential, arbitrary file path or Backend handle. The Root
validates the typed plan, frozen operation and actual resource scopes before
reserving grants/budget. Normalization receives a bounded, redacted receipt
only after admission and returns `InvocationResult`. Root validates/redacts its
output before one writer transaction commits the Artifact/State mutation,
child Action, Invocation terminal, provenance Facts and any outbox work.
Confirmed replay returns the original output without planning, normalization,
resource effects or another budget/grant use.

Ordinary callback tools use the same frozen redaction policy: bounded JSON
input is schema-checked, redacted and checked again before request journaling
or callback entry; output follows the same sequence before Backend terminal
publication. Duplicate JSON keys, non-finite numbers, invalid encoding and
post-redaction expansion beyond 1 MiB fail closed. Validation/callback
exceptions remain fatal under replay, even when ordinary tool errors are
allowed by the Loop. The immutable invocation_finished Fact records the
host_activity_exception reason; no callback is rerun to discover its class.

Ordinary Artifact access checks `capability.invoke` at the actual
`ARTIFACT_KIND`; publication additionally requires `artifact.put` there.
Restricted content has no ordinary read fallback. State permissions target
the exact owning Capability (`CAPABILITY`) or this installation (`HARNESS`)
for Composition-owned State. Immutable birth Facts establish Realm membership;
matching owner names or numeric revisions never establish it. The initiating
Actor and installation Service each require both invocation and resource
authority. Service grants must belong to the frozen activation generation;
terminal commit rechecks the exact reservations, never newer grants.

State reads use the Task's frozen revision or its own committed overlay.
Writes require the expected revision and independently captured CAS revision;
concurrent movement, migration or schema change is a conflict, never a merge.
State is JSON with a frozen schema Artifact. Output is validated, redacted with
the frozen Context policy, and validated again before publication. Session
transcript/journal State is reserved for its controller and cannot be mutated
through model-dispatched resource tools. JSON/UTF-8 resource content and tool
results are bounded to 1 MiB. Unsupported serializers, restricted content and
Scratch placements fail closed.

These are internal Meta operations, not external Backend effects. InMemory or
trusted in-process execution does not become a Managed sandbox. Scratch,
ordinary management-plane State commands, sessions, production Provider and
Evolution remain separate requirements. Release/dependency gates stay open
until their actual installed consumer proofs exist.
