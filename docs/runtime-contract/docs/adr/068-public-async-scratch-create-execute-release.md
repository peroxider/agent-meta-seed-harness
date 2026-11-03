# ADR 068: Public asynchronous Scratch creation, execution and release

Status: Public API 1.13 candidate verified in Windows/Linux installed development
profiles. Seed pin/contract publication remains pending.
Full Scratch, RP-04, S05 and release gates remain open.

The SDK adds three immutable, secretless plans from `agent_meta_runtime.sdk.host`:

| Plan | Resource contract | Required permissions | Effects / idempotency |
| --- | --- | --- | --- |
| `ScratchCreate(idle_ttl_us=1800000000, wall_ttl_us=14400000000)` | `scratch.create/v1` | `scratch.create`, `scratch.execute` | `process.spawn` / KEYED |
| `ScratchExecution(session_id, source_artifact_id, deadline_at_us, timeout_us=30000000)` | `scratch.execute/v1` | `scratch.execute` | `external.irreversible` / KEYED |
| `ScratchRelease(session_id)` | `scratch.release/v1` | `scratch.release` | `external.irreversible` / KEYED |

Every call additionally requires `capability.invoke` on its frozen Capability.
Execution requires Artifact-kind access for the actual Source. Both Actor and
Harness Service must have the exact scoped grants; an execution certificate is
only an upper bound and cannot replace a grant. Source/session identity, Actor,
Realm, Composition, Epoch, deadlines and activation generation remain Root checks.
Budgets/deadlines use strict integer validation; zero is an expired deadline.
Session lifetimes cannot exceed the fixed idle/wall profile. Native lifetime is
bounded by the journal's absolute lifetime, including startup time.

Plans use the existing `ResourceAdapter(prepare, normalize)` interface. Package
callbacks remain synchronous and pure planning/normalization functions. The Host
awaits its own asynchronous `ScratchResourceHost` port between those callbacks.
No package callback, writer transaction or Root/Provider credential enters the
kernel. Generic Backend process/isolation/quota features are not upgraded by
this separate trusted Scratch resource. Optional ipykernel/Curve/native owner
prerequisites must be available; unsupported prerequisites fail closed.

The private certified path from ADR 067 now feeds the public facade. Creation
reserves a Root workspace/session and verifies a scoped Service token before
filesystem/native startup. Execution verifies another token after waiting for
the owner lock. Release verifies current scoped authority, persists its cleanup
plan, stops the actual native process tree, checks the resolved owned child path,
removes the workspace and only then confirms RELEASED. Repeated release does not
repeat the cleanup effect. Normalization failure after creation reaps the new
owner/workspace; execution normalization failure retains its known native effect.

Root records native outcome before output policy/normalization. Each stream is
a separate bounded JSON Artifact (`scratch-stream/v1`, with `channel` and `text`);
each display is a bounded JSON Artifact containing its sanitized MIME bundle.
Frozen Task policy redacts content before publication. JSON framing and policy
expansion count toward each stream's 1 MiB ceiling; displays share a 1 MiB total.
All truncation is explicit. The bounded execution receipt contains references,
session/Source identity, cell ordinal, execution count and sanitized error type.
It contains no path, process handle or live value. Output publication records the
actual child Invocation, all output references and frozen redaction profile.

Binding-name metadata is currently conservative: newly visible names are listed
as declared; existing visible names are listed as potentially changed with
`binding_change_precision=CONSERVATIVE`. Inventory truncation is explicit. This
does not close the normative authoritative binding metadata/inspect requirements.
Public bindings, safe inspection and source-only candidate export remain absent.

Session ownership remains scoped to the creating Principal/Realm/Composition/
Epoch. Callers should explicitly release sessions before retiring that execution
scope. Daemon shutdown reaps its owned kernels and workspaces; restart never
adopts a heap, marks unfinished journal cells NOT_DISPATCHED/UNKNOWN and expires
handles. Explicit release owns recovery cleanup. This assumes the exclusive
daemon lock and the verified native Job/parent-death ownership contract.
Legacy direct-SQL, in-process Scratch sessions are not adopted by this path.

The scheduler sends cancellation once and permits awaited interrupt/cleanup to
finish. Native release cleanup is protected against cancellation while deleting
the audited workspace. For concurrent control, use a separate SDK connection:
the transport serializes requests, so cancellation queued behind a long WaitTask
on the same connection cannot reach the server until that request completes.

New initialization certificates include these three Scratch permission names;
the bootstrap Service grant remains minimal. Existing certificates with only
model/capability permissions cannot authorize Scratch; explicit certificate
provisioning/rotation is required, never an implicit broadening at daemon start.

Signed package tests exercise only public SDK imports and the opaque facade.
They cover actual creation/execution/release, output read/hash verification,
redaction, truncation, normalization failure, missing grant declarations,
repeated release, confirmed replay and public cancellation. Some Root-owned
fault/phase assertions inspect internal state; they are not Seed consumer proof.
Seed pin/contract archive and its installed consumers must be updated separately.

The asynchronous conversion preserves Meta resource replay and validation
semantics. Their regression hooks now await the private method. Artifact text
publication also supplies the final media type at INSERT, preserving immutable
Artifact identity instead of attempting to update it after registration.
