# ADR 057: Frozen Provider admission and controlled daemon assembly

Date: 2026-11-01
Status: loopback TEST assembly implemented; real Provider/Managed admission OPEN

## Decision

Configured calls use internal `provider-reservation/v2`, adding the exact
`configuration_fact_id` and absolute `deadline_at_us` to the existing profile,
tokenizer, price, request hash and firm maximum amounts. Internal unconfigured
v1 accounting remains readable; the public configuration-aware assembly always
uses v2. No public DTO field, SQL schema or API minor version changes here.

Within the Invocation writer transaction, Root reloads the actual committed
Task acceptance View and frozen approval Fact. It checks Realm/Epoch, Actor,
Action, serving Composition/revision, package and model Capability, approved
profile and credential handle. The installation must remain available and its
latest configuration must still equal that frozen enabled approval. The
complete verified Artifact closure, exact request/policy/limits/deadline and
independently recomputed input/output/maximum cost must match. These checks
precede Invocation creation, budget increments and Actor/Service grant uses.
The same checks run again in the dispatch-authorizing writer transaction.
Rotation, disable or late approval cannot lend a newer binding to an older Task.

Confirmed replay checks the original durable reservation and returns its
committed output without another model dispatch, model count or invocation
grant use. A control-plane access check can still consume a `host_control`
use. Replay reuses the original absolute deadline when rebuilding the request
identity; it does not invent a new relative deadline. An unfinished authorized
attempt remains unknown and cannot be resent by a new controller/session.

The Root-owned `ControlledConfiguredProviderHost` composes profile preflight,
approved credential metadata, firm reservation, certified owned-process worker,
normalization and settlement. Credential presence is checked without plaintext
resolution before a fresh reservation. The worker receives only the Realm's
Provider store and public trust material; Root and Service key stores are
excluded. Plaintext resolution remains after worker authorization and TLS.

Root reads original wire usage under frozen pricing and replaces any package
usage/cost claim in both the normalized response and ledger. It revalidates the
output schema after replacement. A bad package normalizer/schema cannot erase
independently known billing. Missing usage stays unknown and retains the
maximum liability; overrun is recorded and prevents successful delivery.
Unsupported wire billing semantics retain unknown usage rather than zero.

## Explicit test boundary

At this checkpoint, only an embedded Root constructor with an explicit bounded
`controlled_provider_test_ca` assembles this path. It has a separate frozen Host
profile hash, `provider_execution=CONTROLLED_TEST_ONLY`, loopback-only network
ranges and synthetic `TEST` pricing. Public HTTPS, other currencies, missing
exact tokenizer/pricing and mismatched Context tokenizer fail preflight. The
normal daemon configuration and ordinary CLI cannot select this test assembly.
InMemory plus this test option is refused. Default Host profiles remain
unchanged and do not execute configured Providers.

[ADR 058](058-explicit-native-provider-test-launch.md) subsequently adds an
explicit native test launcher for independent consumers, preserving these gates.

The external package still runs in the explicitly trusted in-process Host.
Native worker ownership and protected store use do not provide a Managed
sandbox or network isolation for that package. Backend security feature claims
remain unsupported. The bounded worker controller accepts at most 128 distinct
requests during its lifetime and fails closed when exhausted; this is a test
assembly, not an unbounded production service or automatic retry mechanism.

## Evidence

Actual signed package/approval/Task IPC tests reach the owned native process
and a synthetic local TLS server. They cover success, Root replacement of a
false zero-cost claim, unknown usage, overrun, invalid normalization with known
billing, accepted disconnect, cancellation and missing credentials before any
Invocation. They observe process exit, exact frozen View/profile/approval and
no credential in Facts. Separate real writer tests cover substituted profile,
price, tokenizer, cost, request, handle and deadlines; disable/rotation before
reservation and between reservation and dispatch; late approval; and confirmed
replay after disable. Existing worker, journal, cancellation and commit-failure
tests remain separate supporting evidence.

Production EffectIntent/Managed placement, real exact tokenizer and tariff,
the selected model's reasoning/billing profile, full configured process-death
and recovery evidence, captured R2 and bounded authorized live testing remain
required. This is neither a real gateway compatibility claim nor RP-03 closure.
Independent Seed consumption and its release/support evidence are unchanged.
