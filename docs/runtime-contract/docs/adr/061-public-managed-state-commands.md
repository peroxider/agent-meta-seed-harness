# ADR 061: Public managed State initialization, audited snapshots and CAS writes

Status: implementation in progress; S05/S06 and RP-04/RP-05 remain open.

Public API 1.12 adds `State.Create`, `State.Get`, and `State.Write`, using the
existing `CommandRequest/MutationResponse` messages. These are management
operations, separate from the Task resource SPI. `State.Get` is an audited
snapshot command (`state.read/v1`): a fresh command checks `state.read`, reserves
one grant use, records a `state_accessed` Fact and returns immutable revision
references. Replaying its exact signed command returns the original snapshot
without another use or a new read of the current head. It therefore supports
bounded grants without a read-only counter bypass. No State content or command
signature is copied into Facts; content remains an ordinary bounded Artifact.

Creation takes a caller-prepared State ID, owner, JSON schema Artifact and
content Artifact. Optional purpose is GENERAL, SESSION_TRANSCRIPT or
SESSION_JOURNAL. The server derives the controller principal from the signer;
the client cannot nominate another controller. A Capability owner must belong
to a non-uninstalled installation in the endpoint Realm. A Composition owner
must have a unique installation in that Realm. Resource targets are the exact
CAPABILITY or owning HARNESS, never a caller-supplied target string.

`state.write/v1` includes expected_state_revision_id, expected_cas_revision,
schema_id and content_artifact_id. The schema is fixed for ordinary writes;
migration is separate. Schema validation, minimum/stricter pinned redaction,
validation after redaction, derived Artifact publication, immutable revision,
CAS reference/history, Fact and command receipt share one writer transaction.
Uncommitted CAS/schema/authority conflicts never auto-merge. Committed replay
precedes mutable owner/grant/ref checks and returns the original resource,
including after revocation, schema changes or response loss.

Creation pins a validated redaction-policy Artifact in the immutable birth
Fact (default: the existing minimum Context redaction policy). Public writes
and Task resource writes both honor it. Schema and policy Artifacts are GC
roots. Unsupported serializers/assertions, restricted Artifact fallback,
cross-Realm owners and unknown payload fields fail closed. Resource content
is bounded to 1 MiB and schema traversal is bounded independently.
Nullable type unions are supported; schema/data structures have independent
2048/8192 node ceilings and 32/48 depth ceilings. Enum/const caches live only
for one validation call. Redaction patterns cannot repeat, and expansion is
checked before publication. State writes can cite a same-Realm Task Action as
causal parent, with Actor/Root ownership checks and immutable causal edges.

Protected session State is readable/writable through management commands only
by its immutable controller or the current Epoch Root operator. Model tools
cannot read or write protected transcript/journal State; their Context must
use an explicitly reviewed projection instead. This prevents a model tool
from exposing replay signatures or coordination fields as ordinary history.

The SDK publishes envelope builders and convenience methods. The CLI supports
create/get/write and local `--dry-run` envelope output; replay uses the existing
public execute_command mechanism, never private store access. The feature does
not create sessions, relax the five-minute freshness requirement for a new
uncommitted signed command, implement State migration/rollback, or claim
Scratch/Managed isolation. Those requirements need their own evidence.
