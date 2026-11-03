# ADR 040: Public Task execution inspection

Date: 2026-10-30
Status: accepted for implementation; external recovery and release gates remain OPEN

## Decision

Public API 1.2 adds `agent_meta.public.v1.Task.GetExecution`, using the existing
`GetTaskRequest` and `ResourceResponse` protobuf messages. No field number or
permission is changed. The SDK exposes `get_task_execution(task_id)` and CLI
exposes `task execution <task_id>`. Negotiated minors below two cannot call it.
This Public API minor is distinct from the still-unpublished Host SPI version.

The new `task-execution/v1` resource has schema version one. It includes Task
status, frozen input/Surface/State/package-acceptance references, accepted and
current observation revisions, accepted/consumed budgets, root Action, durable
Invocation metadata and Context projection manifests. Invocation metadata is
limited to identifiers, kind/target/attempt/status, request/output ArtifactIds,
projection ID, normalized usage/error codes and timings. Provider-native objects,
backend handles, credential material and raw input/output contents are excluded.
Projection manifests expose ordered provenance/hash/count metadata, not source
Fact payloads or rendered content. Unknown usage remains null.
Persisted/public ProjectionManifest fields now match §41.12 exactly, including
the language-neutral section key `renderer`; the Python DTO retains its explicit
`renderer_artifact_id` attribute. Internal replay/diagnostic fields use only
`x_` extensions and do not participate in identity. The assembled profile hash
includes this encoding revision, so an earlier incompatible development Task
cannot silently recover with different invocation identity semantics.

Like existing Task.Get/Graph queries, this is a local operator read behind the
authenticated same-owner IPC boundary. It is not a new Harness execution
capability, restricted Artifact read authorization or process isolation claim.
Only the daemon's realm is queried. The read performs no mutation, authority-use
reservation, command claim, CAS publication or provider callback. A handler reads
the Task, invocations and projections without awaits, using the daemon's serialized
store owner. The resource records the observed meta revision.

Results are deterministic in durable invocation/start/identity and projection
creation/identity order. The initial bounded query allows 1,000 invocations,
64 projections and at most 1 MiB of resource JSON. Exceeding a ceiling returns
RESOURCE_EXHAUSTED instead of an incomplete successful response. A missing or
foreign-realm Task returns NOT_FOUND. Existing Task.Get/Wait responses are unchanged.

## Purpose and evidence

Independent consumers need to distinguish confirmed Invocation results from
in-flight UNKNOWN outcomes before stopping an owner, and compare invocation IDs,
output references, consumed budgets and projection identities after restart.
Causal graph node counts alone cannot establish those states. This method makes
the actual durable records reviewable without exposing DB/CAS paths or requiring
private test hooks. It does not itself prove recovery or close RP-02/RP-04.

Required Runtime proofs cover real signed AMPAK execution/replay metadata,
read-only behavior, query bounds, missing/foreign Tasks and old-minor refusal.
Seed must repin the wheel and run independent process-loss proofs before a
dependency can be VERIFIED. Artifact contents, State/Scratch operations and
historical Evolution queries remain separate interfaces.
