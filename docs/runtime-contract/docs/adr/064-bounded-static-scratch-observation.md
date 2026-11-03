# ADR 064: Bounded static Scratch observation

Status: private observation mechanism verified in development. Public Scratch Host admission,
durable binding provenance, source export and S05/RP-04 remain open.

The independent kernel exposes a fixed authenticated control request for
bindings and safe inspection. It does not evaluate a generated inspection cell,
expression, attribute path or serialized object. Inspection accepts exactly one
identifier or session-scoped weak handle, plus a fixed depth/item/byte/time
budget. The kernel refuses observation while caller code runs. The owner also
serializes these requests with cell execution and checks the actual cell order.
Only bounded canonical JSON bytes return to the owner; no live value crosses.

The existing SafeReflector was insufficient for this path: isinstance-based
scalar handling could execute subclass hooks, dictionary access could invoke a
user descriptor, metadata lookup could invoke a metaclass, per-container limits
did not enforce global item/byte budgets, and stale weak registry entries were
not removed. The implementation now uses exact builtin types and builtin type
storage, avoids equality lookups on hostile class namespace keys, and denies
unrecognized or hidden dictionary descriptors. It does not call repr/str,
overridden iteration/length/comparison, instance attribute hooks or properties.
Type-name slots can retain a string subclass assigned with type.__setattr__;
their names are copied through the builtin string operation before rendering.

A shared traversal ledger caps all nodes, labels and payloads. Cycles truncate
without recursion through the same live object. Strings remain at most 4,096
code points, large bytes are not hashed beyond the budget, and final encoded
nodes are checked against the payload ceiling. A fixed truncation marker can
remain when a caller allows fewer bytes than the marker itself. Class/MRO
metadata scanning is bounded and fails closed when incomplete. Exceptions yield
opaque reason hashes without fallback rendering.

Weak handles contain a random reflector-session namespace and expire after
garbage collection, explicit registry clear or worker loss/replacement. Registry
entries and lookup identities are bounded and do not hold the observed object
alive. A handle from another kernel cannot accidentally resolve to its first
new object. Non-weakrefable values remain request-local and receive no handle.

Bindings currently expose at most 100 public identifiers after scanning at most
1,000 namespace entries, exact bounded type module/name and an optional weak
handle. Truncation is explicit. Safe inspection reuses the corrected shared
reflector. Root has not yet attached source Artifact/created/last-changed Action
metadata or frozen redaction policies; these private observations cannot serve
as authoritative provenance, public authorization or promotion evidence.

Actual kernel and pure-domain tests use hook canaries, malformed requests,
global budgets, cycles, oversized bytes and deleted/replaced weak objects.
Installed-wheel Windows/Linux cohorts must be recorded separately from earlier
process-foundation and Seed cohorts. No public capability or grant is added,
and the public API remains 1.12 until its complete Host path is implemented.
