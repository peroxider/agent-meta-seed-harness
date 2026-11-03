# ADR 062: Ordinary tool child Actions and execution-token bindings

Status: implementation in progress; S05/RP-04 and production isolation remain open.

Each newly admitted ordinary callback tool receives its own child Action,
inside the same writer transaction as Invocation creation, budget and Actor/
Service grant reservation. The immutable action_started Fact records caused_by
to the Task root, authorized_by to the exact reserved grants and used to the
redacted request Artifact. Invocation part_of/produced edges complete the
output provenance chain. Resource tools retain their existing child semantics.

Success, ordinary tool error, callback/schema failure, cancellation and unknown
recovery terminate the child along with its Invocation. Budget refusal rolls
back the child and reserved grants. Confirmed replay reuses the original child,
Invocation and output; it does not create another Action or reserve again.
Legacy confirmed root-bound Invocations retain their historical identities.

InMemory execution tokens bind the actual admitted Action: Task root for MODEL,
child for CAPABILITY. Root derives it from its own Invocation/Action/Task rows
and checks Task, Actor, Realm, Composition, target and parent relationship
before issuance and again during authorization commit. A token still signed
for the Task root cannot authorize the child callback. Package code never
selects an Action ID or receives token/key/Backend handle material.

This is an implementation of the existing public causal/token contracts, with
no new RPC, protobuf field or SDK method. Public API remains 1.12. The new
development wheel and decision archive must be pinned by hash and independently
tested; older consumer cohorts must not be relabeled. Neither child Actions nor
InMemory execution establish Managed isolation or an independent Scratch worker.
