# ADR 046: Bounded public Task state trace

Date: 2026-10-31
Status: accepted for implementation; external acceptance/release gates OPEN

## Decision

Public API 1.5 adds read-only `Task.GetTrace` using the existing
GetTaskRequest/ResourceResponse messages, SDK `get_task_trace(task_id)` and CLI
`task trace <task-id>`. The resource type is `task-trace/v1`, schema version one.
No protobuf field number, command permission, execution facade or support claim
changes. Negotiated minors below five refuse the method before dispatch.

This uses the existing authenticated same-owner local administration boundary,
restricted to a Task in the daemon's Realm. It returns current Task/Action
statuses, ordered persisted Fact metadata and causal edges whose source Facts
belong to that Task or its Actions. Metadata contains Fact identity/sequence,
entity/event/schema/action identity, recorded time and only the optional
old_status/new_status/reason_code payload fields. Missing fields remain null;
the reader never invents historical transitions from a current status. Raw
payloads, input/output content, keys, native objects and backend references are
not exposed. This is not a general Fact/Evidence/Evaluation query API.

All rows are read in one SQLite snapshot with an explicit Fact sequence
boundary and meta revision. No callback or await spans that snapshot. Limits
are 1,000 Actions, 4 MiB source Action bytes, 4,000 Facts, 4,096 edges, 8 MiB aggregate source Fact payload
bytes and 4 MiB encoded response; exceeding any limit fails without a partial
success. Reads do not add commands, uses, artifacts, Facts or revisions.

Independent Seed determinism proofs may normalize generated IDs, absolute
timestamps/sequences and observation revisions, but must preserve actual event
order, statuses/reasons, actor/target/budget semantics and content ArtifactIds.
They must separately compare the frozen inputs and rendered Context rather
than infer equivalence from terminal status. They cannot claim AC-M17's InMemory
Backend merely because this trusted in-process Host exists.

## Proofs

Runtime proofs cover real signed Task creation, exact persisted trace rows,
read-only snapshot behavior, missing/foreign Realm Tasks, malformed metadata,
every bound and old-minor refusal. External proofs must run installed wheels
and use public reads, their own signed Actor and actual AMPAK callbacks. Full
NFR-M48/AC-M48 and release evidence remain separate requirements.
