# ADR 052: Durable Provider invocation accounting

Date: 2026-11-01
Status: internal Host implementation; public Provider admission and RP-03 OPEN

## Decision

The Host admits a Provider call in one SQLite writer transaction with its
Invocation, attempt, Task/Action counters and Actor/installation-scoped Service
grant uses. Before any worker request, the journal retains the exact frozen
profile, pricing and tokenizer artifact references, wire request hash, exact
input count, maximum output count and maximum cost. All amounts are bounded
non-negative integers; missing pricing/tokenizer evidence is not zero pricing.
The internal DTO carries evidence previously verified by the enforcing
coordinator. Constructing the DTO alone does not verify a profile or tokenizer.

The journal adds a private `provider` member to `host-invocation-journal/v1`.
`provider-reservation/v1` and `provider-settlement/v1` do not contain credentials,
worker frames or raw responses. Two additive invocation Fact events,
`provider_cost_reserved` and `provider_cost_settled`, anchor the journal projection
in the existing immutable Fact chain. Reads verify the projection and terminal
usage against these Facts. No SQL migration or public Host DTO is added here.
The reservation is not an EffectIntent and does not satisfy its dispatch rules.

Cost admission adds the known settled liabilities and every outstanding maximum
reservation, then applies the lesser Task and loop-policy ceiling. Prior calls
with unknown cost and no durable reservation deny admission. A model call without
a Provider reservation cannot bypass a previous UNKNOWN/overrun. Amount-limited
authority grants remain refused by this Host until grant amount accounting is
implemented. Permission matching never silently drops a resource ceiling.

Several permissions covered by one grant consume one use per admitted invocation.
Selection and reservation remain atomic for both principals. A budget denial or
failed transaction leaves no grant use, Invocation, counter or accounting Fact.
An orphan CAS blob staged before the transaction remains ordinary GC input.

A proven NOT_SENT terminal releases the cost hold and records zero billed cost;
it does not refund call/effect/use counters or authorize resending that attempt.
A confirmed response with known billable cost replaces its maximum hold with
the actual cost. Missing usage retains the hold; reported zero stays distinct
from unknown. UNKNOWN keeps at least the reservation, preserves any greater
reported liability, reports the Task total as unknown, and blocks further calls.
Token or cost overruns are recorded faithfully, never clamped, and block further
admission or replay of a successful overrun result. A stale or contradictory
terminal cannot overwrite the first committed terminal. Exact terminal replays
do not emit another Fact or charge another use.

On a new Host/SQLite connection, confirmed invocations replay from the journal.
An unfinished attempt never causes another worker submission. Task recovery or
cancellation commits EXTERNAL_EFFECT_UNKNOWN and retains the hold when there is
no stronger durable terminal evidence. No automatic retry attempt is introduced.

## Evidence and remaining work

`tests/unit/test_provider_accounting.py` uses actual SQLite transactions, grant
selection/counters, immutable Facts, CAS and a reopened database connection. Its
price/tokenizer references are synthetic fixtures, not live compatibility proof.
Checks cover transaction aborts during admission/settlement, ceilings, terminal
replay/conflicts, projection tampering, UNKNOWN, NOT_SENT, missing usage and
token/cost overruns. Existing trusted/in-memory Host regressions remain required.

The public profile/credential registration, exact-tokenizer/pricing verification,
EffectIntent authorization/dispatch, the public binding of the
[integrated certified worker edge](053-provider-dispatch-and-durable-terminal-edge.md),
public Host plan/normalizer bridge, real process-kill
integration, R2 capture and explicitly bounded live job still require assembly
and evidence. This ADR does not mark S04/RP-03 complete, update the Seed-pinned
Runtime wheel, or assert any live Provider/platform support.
