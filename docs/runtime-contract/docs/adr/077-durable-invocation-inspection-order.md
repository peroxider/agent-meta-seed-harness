# ADR 077: Durable Invocation order in Task execution inspection

Status: Implemented development candidate; installed verification in progress.
Public API remains 1.16.0. No RPC, entity, schema column or permission is added.

## Problem

Independent Linux Seed consumers observed successful Tasks whose execution
inspection listed MODEL, MODEL, CAPABILITY instead of their actual serial
MODEL, CAPABILITY, MODEL history. The v1 query ordered by wall-clock start time
and identity. Neither wall-clock monotonicity nor identity order establishes
the committed order of Invocation creation. Clock regression can reorder
different timestamps; equal timestamps allow identities to decide the result.

## Decision

Task.GetExecution orders Invocation rows by their immutable `invocation_created`
Fact sequence in the Task's Realm. That sequence is recorded by the existing
canonical creation transaction and survives restart. The indexed Fact lookup
also fixes entity type, identity and event type. It selects the earliest
matching creation Fact and cannot multiply Invocation rows.

Rows without a creation Fact retain deterministic start-time/identity order
after rows with a creation Fact. This legacy/fault-fixture fallback does not
claim a causal order for records without authoritative creation evidence.
Start and completion timestamps remain unchanged metadata. No execution,
replay, reservation, terminal result or budget is modified by this read.

Existing Realm scoping, 1,000-Invocation/64-projection/1 MiB ceilings and
read-only behavior remain enforced. This clarifies the durable Invocation order
in ADR 040; it does not change the ordering contract of other query resources.

## Evidence required

Runtime regressions use canonical command mutators with decreasing and equal
transaction times, and deliberately reverse identity order. Both fail against
the previous installed wheel. The corrected query must preserve creation order,
the original timestamps and exact repeated/reopened query results without
writes. Existing query bounds and missing/foreign Realm checks remain required.

Independent installed Seed NFR-M48 and confirmed-State-tool recovery checks
retain their strict ordered MODEL/CAPABILITY/MODEL assertions. Earlier failed
consumer reports remain preserved. Wheel/input hashes and affected/full-run
scopes must distinguish pre-fix and corrected verification. These development
proofs do not close S04 live, World isolation or release gates.
