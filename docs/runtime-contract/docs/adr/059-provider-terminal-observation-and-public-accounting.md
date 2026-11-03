# ADR 059: Durable Provider terminal observations and public accounting

Date: 2026-11-02
Status: API 1.10 implemented; real Provider/placement/release gates remain open

## Problem and decision

The controlled HTTPS edge already returned bounded HTTP status and Retry-After
metadata, but the Host discarded it when settling the Invocation. A 429 could
therefore appear only as RESOURCE_EXHAUSTED, losing the upstream retry hint.
This also left operators without a public view of conservative reserved cost.

API 1.10 adds an optional `provider` member to each applicable Invocation in the
existing `task-execution/v1` JSON resource. No RPC, proto field number, SQL table
or permission is added. Legacy records without transport observations remain
readable; missing metadata is null, never invented from an error code.

The member contains the frozen profile and configuration Fact references,
input/output/maximum-cost reservation, conservative settlement and optional
terminal observation. Settlement distinguishes known zero, unknown cost,
maximum liability, overrun and UNKNOWN external outcome. It is the same durable
accounting used for admission, not a new estimate or a package-reported bill.

## Terminal observation contract

Internal `ProviderTerminalObservation` permits only transport state, a registry
error code, optional integer HTTP status (100–599) and optional integer
`retry_after_us` (0–3600000000). Booleans, arbitrary error text, headers, raw
response content, native handles and signature bytes are not accepted. A retry
hint requires an HTTP error observation; it is advisory data, never authority
to retry. NOT_SENT requires a stable error; UNKNOWN requires
EXTERNAL_EFFECT_UNKNOWN.

Root binds this data to the admitted request ID and full request scope hash,
and appends `provider_terminal_observed` with
`provider-terminal-observation/v1`. Observation, cost settlement, usage,
output/error and Invocation terminal commit in the same writer transaction.
An aborted commit leaves neither observation nor settlement. Replaying the
same terminal does not append another Fact; different supplied metadata is an
IDEMPOTENCY_CONFLICT.

The mutable `provider_terminal` journal projection is checked against exactly
one immutable Fact and the original reservation and settlement. Public
inspection validates the complete accounting/observation relationship before
returning any Provider projection. A missing Fact, injected field, changed
request/hash/hint or inconsistent outcome fails with INTEGRITY_ERROR. Existing
append-only database triggers also reject rewriting or deleting the Fact.

The observation describes the transport terminal. It does not overwrite a
normalization/schema failure or usage overrun detected after a valid response.
Crash recovery has no newly observed HTTP terminal and retains null metadata
plus UNKNOWN liability. No raw response is retained to manufacture one.

## Rate limits and scope

An actual controlled 429 is still RESOURCE_EXHAUSTED, now with its bounded
Retry-After visible through `Task.GetExecution`. Unknown cost retains its
maximum reservation instead of becoming zero. The existing
UNAVAILABLE_NO_RETRY policy and durable dispatch guard remain unchanged; a
hint does not create another attempt or release a grant/call/effect count.

Tests cover actual TLS/owned-worker 429 responses, public signed daemon Task
queries, reopen persistence, no retry, append-only Fact protection, projection
tampering, transaction abort, idempotent/conflicting replay and invalid metadata.
These remain synthetic loopback TEST evidence. Exact real tokenizer/tariff,
selected-model reasoning semantics, EffectIntent/Managed placement, captured R2,
bounded authorized live testing and release review remain required for RP-03.
