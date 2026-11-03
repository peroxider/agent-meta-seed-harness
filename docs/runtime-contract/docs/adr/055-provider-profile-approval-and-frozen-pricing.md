# ADR 055: Operator-approved Provider profiles and frozen pricing

Date: 2026-11-01
Status: API 1.8 approval/data contracts implemented; configured execution OPEN

## Decision

Public API 1.8 adds `Harness.ConfigureProvider` using the existing
CommandRequest/MutationResponse messages. It accepts the signed payload
`harness.configure-provider/v1` with exactly `harness_id`, `capability_id`,
`profile_artifact_id`, `credential_handle`, `enabled` and
`expected_configuration_revision`. The envelope must also carry an expected
Realm meta revision. SDK `prepare_harness_provider_configuration` returns the
complete signed, reviewable, persistable command; `configure_harness_provider`
prepares and executes it. No secret material or secret-derived identifier is
accepted in this operation. The credential identifier must be a native store
handle with its UUIDv4 shape.

The existing `harness.activate` permission is checked against the exact HARNESS
target. Credential rebinding additionally requires the current Epoch's Root
operator principal, both at the public handler and in the writer transaction.
A delegated activation grant, including a correctly scoped one, does not
authorize choosing another protected credential. The permission vocabulary is
unchanged; no broad credential authority is implicitly delegated.

An enabled approval requires a valid package from an explicitly trusted
publisher. The package metadata and its exact model Capability descriptor must
declare the requested `provider_profile_artifact_id`; the model slot,
descriptor revision and code Artifact must belong to that installation. The
operator cannot bypass these signed declarations by signing a different
profile/capability request. Public HTTPS profiles require a Windows DPAPI handle;
test/insecure handles cannot be promoted by that profile label. Approval does
not resolve a credential or verify that a handle is currently provisioned.

The single writer transaction appends a `provider_configured` Harness Fact with
`harness-provider-configuration/v1`, monotonically increasing configuration
revision, Realm Epoch, installation/package/Capability/profile identity,
opaque handle, enabled flag and the complete verified Artifact closure. It
does not create a Task, Invocation, EffectIntent, Composition, instance, Service
grant or network request. Authority use, revision checks and the Fact commit
atomically. A replayed committed command returns the original receipt without
another use, including after actual daemon restart. Uninstalled packages cannot
be resurrected by configuration. Disable identifies the existing binding and
can revoke its enabled approval without rereading damaged dependency bytes.

`Harness.Get` adds optional `provider_configuration` metadata. `enabled` denotes
operator approval of a binding, not operational readiness or execution support.
Task acceptance freezes its exact `provider_configuration_fact_id` in the
existing acceptance View. A later configuration/handle change does not mutate
that Artifact or retroactively authorize an older Task. GC's existing exact
Artifact reference scanner pins the complete verified closure through the Fact.
No new SQL table/migration or proto field number is introduced.

## Frozen profile data

`provider-profile/v1` is a canonical bounded object with exactly these fields:

```text
schema, protocol, model_id, parameter_allowlist, context_window_tokens,
maximum_output_tokens, maximum_request_bytes, maximum_response_bytes,
timeout_us, egress_policy_artifact_id, tokenizer_artifact_id,
price_policy_artifact_id, lookup_policy, usage_mapping
```

The initial protocol is `anthropic-messages-terminal/v1`, usage mapping is
`anthropic-messages-usage/v1`, and lookup policy is `UNAVAILABLE_NO_RETRY`.
Parameters are sorted unique allowed terminal Messages fields. Byte limits are
at most 1 MiB, timeout at most 300 seconds, output limit positive and no greater
than the context window. Documents reject duplicate/unknown fields, nonfinite
numbers, depth over 32 or more than 16384 nodes. Every referenced byte sequence
is verified against its ArtifactId before use. The egress reference uses the
existing `provider-egress/v1` HTTPS host/port/path/network/profile document.
No profile data can load Python code or silently select another transport.

`provider-tokenizer/v1` contains exactly `schema`, `model_id`, `algorithm` and
`tokenizer_id`. A declaration is not implementation availability. The current
local counter is `CONTROLLED_TEST_UTF8_BYTES_V1` with `utf8-bytes/v1`, restricted
to CONTROLLED_TEST_ONLY policies and synthetic input fixtures. Public profiles
and unknown implementations fail preflight; this counter never approximates a
real GLM tokenizer. Null tokenizer/pricing references represent unavailability
and remain FAILED_PRECONDITION before any model reservation.

`provider-price/v1` contains exactly `schema`, `currency`, `pricing_version`,
`input_microunits_per_million_tokens`, `output_microunits_per_million_tokens`,
`minimum_cost_microunits` and `rounding`. Rounding is explicitly
`CEIL_EACH_DIMENSION_MICROUNIT`; arithmetic uses bounded non-negative integers
without floating-point conversion. Cost is the greater of the declared minimum
and the two per-dimension rounded costs. A missing token dimension leaves cost
unknown, even when another dimension is known zero. A maximum is derived only
from a verified exact input count and requested output ceiling under this
frozen policy. The currency is part of the policy; no exchange rate or actual
vendor tariff is inferred by Runtime.

The narrow input profile supports text, basic function-tool definitions and
serial tool-use/result history. Server tools, image/reasoning/cache features,
unknown content types and unsupported billing semantics are refused. The
independent wire-usage reader checks model identity and known terminal response
fields, rejects unsupported/unknown usage dimensions, and computes usage/cost
from the original bounded response and frozen pricing. A package normalizer's
cost field is not a source of billing authority. Known zero, missing usage and
unknown cache usage stay distinct. The execution bridge still must apply this
reader to both the durable ledger and normalized response before releasing a
reservation; implementing the reader does not imply that bridge is assembled.

## Evidence and remaining work

Profile/pricing unit tests use synthetic policies and cover immutable content
closure, integer rounding/minimum/overflow, unknown usage, unsupported tokenizers,
parameter/content/billing rejection, model binding and integrity failures.
Public configuration tests use actual signed packages, IPC, authority checks,
SQLite writer transactions, daemon restart, ordinary Artifact reads and GC
marks. They cover Root-role/scoped-grant refusal, payload tampering, stale/missing
guards, raw-secret handle rejection, disable, no resurrection, frozen old/new
Task Views and approval without executing a Provider.

Protected operator credential provisioning, configuration CLI and read-only
review are implemented in [ADR 056](056-provider-credential-provisioning-and-reviewable-cli.md).
The configuration-aware Root ProviderModelHost/Context/capability-surface bridge,
independent usage settlement in the actual execution path, EffectIntent/Managed
backend gates and full configured daemon recovery/commit/cancellation evidence
remain required. Approving an unready profile still fails before a model
Invocation. No GLM tokenizer, real gateway tariff, captured R2, live request,
paid support, platform product support or RP-03 closure is claimed. The
independent Seed pinned wheel remains unchanged.
