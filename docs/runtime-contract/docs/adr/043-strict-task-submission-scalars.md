# ADR 043: Strict Task submission scalars

Date: 2026-10-30
Status: accepted for implementation; full external admission/fault gates remain OPEN

## Problem and decision

Task admission cast budget/deadline values with `int()` and treated a falsy
deadline as absent. This admitted booleans, strings and truncated fractions;
deadline zero silently became unlimited. That contradicts the existing frozen
TaskBudget/integer-time contract. The SDK also dropped falsy budget values.

Use one pure Task submission parser in the public SDK, CLI and server. The
payload has only `input_artifact_id`, optional `budget` and optional
`deadline_at_us`. Input identity must be an ArtifactId. An explicit budget must
be an object with known TaskBudget fields and exact nonnegative integers;
booleans/floats/strings/null/unknown fields fail INVALID_ARGUMENT. An optional
deadline is absent/null or an exact nonnegative integer. Zero is a real Unix
deadline and therefore expires; it cannot disable the deadline.

The server validates before staging Surface/View artifacts. Exact committed
command replay still returns its recorded result before applying new admission
validation. Existing accepted DTO/execution semantics and protobuf fields do not
change. This is a Public API 1.3 implementation correction, not a new permission
or an implicit budget extension. CLI exposes the existing field through
`task submit --deadline-at-us <absolute-microseconds>`; dry-run uses the same pure
validation and includes the actual deadline in its plan.

Runtime tests must reject malformed signed payloads without accepted Tasks,
counter changes or staged snapshots, and verify deadline zero remains zero.
Independent public-wheel tests must observe already-expired Tasks without model
dispatch, in-flight timeout/cancel propagation and unchanged consumed counters.
These proofs do not establish hard preemption for the cooperative profile.
