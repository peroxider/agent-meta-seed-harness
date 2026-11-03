# ADR 069: Public bounded Scratch bindings and inspection

Status: API 1.14 candidate verified in Windows/Linux installed development
profiles (334 tests each, including 60 actual-kernel cases), with 1449 selected
Root unit tests passing. Evidence: `reports/scratch-inspection-v1-input/verification.json`.
S05, RP-04, source export and Seed publication remain open.

`sdk.host.ScratchBindings(session_id)` and
`ScratchInspect(session_id, name=None, handle=None, max_depth=8,
max_items=10000, max_bytes=1048576, max_ms=50)` use the existing synchronous
ResourceAdapter callbacks and asynchronous Root resource port from ADR 068.
Their contracts are `scratch.bindings/v1` and `scratch.inspect/v1`, PURE with
effect `none`, requiring `scratch.inspect` in addition to scoped
`capability.invoke`. PURE does not bypass tool steps, frozen surface validation,
Actor/Service grants, certificate upper bounds, or immediate dispatch revalidation.
Fresh initialization certificates include `scratch.inspect`; existing certificates
are never widened implicitly.

Inspection accepts exactly one identifier or previously issued weak handle.
It invokes the fixed native observation protocol, never an evaluation cell.
Root validates session ownership, active status, Composition/Epoch and actual
child Action/Invocation before dispatch and publication. The observed native cell
ordinal must agree with Root's immutable admitted cell journal. Root derives
Source, creating/last-changing Action and Invocation from that journal rather
than accepting kernel authority claims. No writer transaction crosses a native
operation. Receipts and used/produced edges preserve the actual inspection child.

CPython 3.12 opcode tracing records name stores/deletes in the user namespace on
the executing cell's main thread, including global writes from called functions.
It does not format constants, hash user code constants, retain binding values,
or call repr. Identity observations supplement the trace. Generations survive
deletion and rebinding. Inventories expose created/last-changing cell and origins,
static type labels and builtin container lengths, never scalar contents as a
summary. Truncated inventories, unsupported interpreters, prior/replaced tracers
and trace bounds make completeness explicitly false. Untracked bootstrap names
are omitted. Heap mutations and other threads remain `UNKNOWN_RISK`; this is
trusted exploration instrumentation, not an adversarial monitor or sandbox.

Safe inspection reuses bounded static reflection. Descriptors, properties,
metaclass hooks and repr are not invoked. Frozen Task policy redacts both values
and sensitive object/dictionary child labels. Public weak references use the
`handle` field; credential fields named `token` remain subject to redaction.
The full receipt is capped at 1 MiB including framing and policy expansion.
Depth/item/byte/time exhaustion is explicit in opaque/truncated nodes.

Root persists hashes of issued handles with their binding origins. Exact indexed
lookup admits at most 4096 live handle aliases per session; older aliases expire.
Native weak-reference expiry invalidates its Root alias and emits an invocation
Fact. No strong heap ownership, raw address or kernel path crosses the facade.
Release/restart invalidates live capabilities; a handle never grants another
session's authority. Durable metadata and Facts remain under normal retention.

Signed package tests cover name/top-level/nested handle inspection, sensitive
fields and hostile hooks, exact source provenance after rebinding, collected weak
handles, reserved-grant revocation, bounded output and invalid expression input.
Root-owned fault assertions are not independent Seed consumer evidence. Candidate
wheel verification must establish identical installed bytes and run native tests
on Windows and Linux before this ADR's status advances. Source-only export and
the Seed pin/contract archive require separate implementation and evidence.
