# ADR 032: Versioned execution-time Harness Host SPI

Date: 2026-10-30
Status: accepted for implementation; RP-01/RP-02 remain OPEN

## Decision

Publish execution DTOs and protocols under `agent_meta_runtime.sdk.host`.
Harness Contract 1.2.0 will advertise Host SPI 1.0.0 only after the bound Host
and public-wheel consumer recovery suite pass. Importability is preparation,
not proof of a working execution channel. Public API v1 RPC method identities
and AMPAK1 encoding remain unchanged.

An AMPAK entrypoint is a synchronous factory `() -> HarnessAdapter`
([ADR 036](036-task-free-factories-and-async-reconciliation.md)); factory/health
creation never manufactures a Task solely for probing.
The adapter contains an async `run_task(TaskEnvelope, TaskRuntime)` function,
one terminal-only model invocation function and a fixed operation-to-tool
registry and a task-free PURE health callback. Runtime loads only explicitly installed content-addressed packages;
there is no Python distribution discovery, pip invocation or source-checkout
fallback. Each code Artifact has a distinct import namespace, so installing a
new version cannot reuse the old version's module objects.

TaskEnvelope contains immutable input bytes and frozen Composition, Surface,
State-revision bindings, acceptance metadata, budget, loop-policy bytes and
deadline. It exposes no connection, repository, credential or live Runtime
object. The TaskRuntime protocol exposes context projection, model invocation,
typed tool dispatch and cancellation checks. It does not expose commits.

The external adapter returns TerminalResult/InvocationResult. The Runtime owns
all Action/Invocation/Projection/Fact/Artifact and terminal transactions. It
reserves counters before external calls, rechecks current Authority/deadline
before each effect, and accepts only tool calls present in the normalized
model response, in response order. A textual command never becomes an effect.

Task-local ordinal request identities and complete normalized results are
durable. On restart, known results replay without execution or double charging;
an in-flight request lacking an authoritative terminal result stops as UNKNOWN.
The consumer cannot turn UNKNOWN into a new model/effect attempt. Terminal
state is irreversible and late completions are auditable observations.

Projection uses the existing ProjectionManifest required fields. The producer
supplies immutable rendered sections and provenance; Runtime allocates the
projection identity and registers content-addressed artifacts. Same semantic
content is compared independently of generated IDs/wall timestamps.

Only an explicitly operator-trusted publisher may use in-process placement.
Other placements require their declared Backend constraints; missing isolation
never causes fallback into the daemon. This SPI does not grant credentials,
network access, State mutation or stronger Backend features by itself.

## Wire-shaped values

Normalized content uses fixed tagged objects (`kind` plus the fields of the
corresponding TextPart/JsonPart/ArtifactPart/ToolCallPart/ToolResultPart). A
`model-response/v1` object has exactly `schema,parts,finish_reason,usage`.
Usage is null or exactly `input_tokens,output_tokens,cost_microunits`, with each
count a nonnegative integer or null (unknown). A `terminal-result/v1` object
has exactly `schema,parts,result_truncated`. Unknown fields/kinds, invalid
JSON arguments, duplicate keys, invalid artifact references and empty terminal
content fail closed. Full ordered part arrays are preserved.

S04 credential/egress enforcement and S05-S07 State/Scratch/Evolution entrypoints
are separate extensions and cannot be inferred from this protocol.
