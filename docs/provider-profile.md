# First Provider profile (S04 development)

The operator selected the existing local Volcano configuration on 2026-10-31.
Its model type is `anthropic`; Sonnet/Haiku map to `glm-5.3-flash`, Opus to
`glm-5.3`. The first planned profile uses `glm-5.3-flash`. The custom gateway
origin remains operator configuration; it is not replaced with an assumed
standard billing endpoint. No credential value or credential-derived hash is
copied into this repository, package, report or fixture.

The initial codec profile is `anthropic-messages-terminal/v1`, terminal JSON
only, bounded to 1 MiB, text and structured `tool_use` blocks, with an exact
model binding. It uses public Runtime DTOs and their canonical validation.
Unknown token usage and cost remain unknown. Unsupported reasoning/server-tool
blocks, nonzero or unknown cache counters, partial output and unknown fields
fail closed. This is a deliberately narrow profile, not general compatibility
with every version of the [Messages API](https://platform.claude.com/docs/en/api/messages/create).
Volcano's [integration guide](https://docs.volcengine.com/docs/ark/integrate-third-party-tools)
describes its compatible protocol. A separate native operator diagnostic on
2026-11-03 observed HTTP 200 from the configured gateway; its scope is recorded below.

On 2026-11-03 the operator explicitly limited real validation to an existing
subscription or free quota, with zero additional charges and no paid fallback
(`provider-usage-authorization.json`). The configured custom gateway is not the
documented official Coding Plan endpoint, so the official subscription-only
billing guarantee is not evidence of this gateway's billing behavior. The
operator subsequently confirmed that this route only consumes existing plan/free
quota, rejects after exhaustion, and explicitly authorized real requests. Billing
authorization is therefore available from that operator attestation; no extra
charge or paid fallback is allowed, and rate limiting must stop validation.
This is not an independent measurement of gateway billing. Exact tokenizer,
reasoning/usage profile and Host admission requirements still gate live Task
integration. No credential or credential-derived hash was recorded. The official
[plan overview](https://docs.volcengine.com/docs/ark/coding-plan-personal-plan-overview?lang=zh)
limits eligible use to coding tools and says exhausted plan quota does not
consume other balances; it must not be applied to an unverified custom route.

`provider-usage-authorization.json` is ignored operator-local state. It is not
distributed as repository authorization. The committed
`provider-usage-authorization.example.json` defaults to no live permission and
an unverified billing boundary; cloning this repository grants no live usage.

The codec performs no HTTP request, credential resolution, retry or recording.
Synthetic protocol fixtures exercise normalization; they are not captured R2
traffic. Minimal's fake Provider and signed execution allowlist are unchanged.
This new code is not activated as a live Provider in the minimal package.

Live readiness remains unavailable until a versioned profile fixes the exact
tokenizer and context/output limits, pricing/usage semantics, retry/lookup
policy and SDK/transport version. Runtime must provide a controlled worker,
scoped protected credential handle, DNS/IP/redirect-aware egress enforcement,
durable attempt/effect accounting, and reservation/settlement. Loop/ordinary
DTOs must never receive plaintext credentials. Missing tokenizer or an unknown
maximum cost under a hard ceiling must fail before a model request. No paid
fallback, complete gateway compatibility, captured replay or product support is claimed.

On 2026-11-01, the [model author's guide](https://docs.z.ai/guides/vlm/glm-5.3-flash)
confirmed that thinking cannot be disabled for GLM-5.3-Flash. The narrow codec
above therefore does not establish compatibility with this selected model.
A separate versioned reasoning/usage profile and its redaction rules are
required. Volcano's [Messages token-count API](https://docs.volcengine.com/docs/ark/messages-count-tokens-api?lang=zh)
is a possible investigation path; it does not prove exact accounting or
availability at the operator's custom gateway. No public catalog tariff is
adopted as that gateway's price.

The installed distribution now also supplies a pinned local text-encoding
preparation utility and data lock for the model author's published vocabulary.
Its native checks do not enable Host admission or count a complete gateway
request. See [local tokenizer preparation](provider-tokenizer-preparation.md)
for the exact author revision, optional binary lock, offline command and
remaining template/Context contract work.

Runtime API 1.9 now supplies secretless plan/normalization callbacks,
Root-operator binding approval, read-only review and native protected credential
provisioning. Its embedded loopback/TEST assembly executes synthetic signed
Provider Tasks and settles original wire usage independently of a package's
cost claim (ADR 051–057 in the contract archive). Default daemon execution,
Seed's minimal package and the real Provider gate remain unchanged. These
Runtime development checks are not independent Seed Provider/live evidence.

## Explicit public Host binding (development)

`providers/messages.py` implements synchronous public `ProviderAdapter`
callbacks. The request uses only issued, hash-checked, redacted Context sections:
system/state/facts become system content, task input becomes the first user
message, and selected Capability schemas become function-tool definitions.
Normalized model history becomes text/structured tool-use blocks; serial tool
results retain IDs/order and stable error codes. Usage/cost and upstream metadata
are not prompt history. Unresolved/reordered/repeated IDs, ordinal drift,
unsupported parts and malformed/oversized history are rejected before a plan.
History is limited to 1 MiB/512 entries; the public plan also bounds the complete
request and message count. No text is parsed as a new tool call.

The immutable constructor contains only profile ArtifactId, model ID and maximum
output tokens. Its terminal callback uses the same strict codec as offline
normalization/replay. Root replaces usage/cost with independently verified wire
accounting. The callback contains no credential, endpoint, HTTP client, retry,
fallback, raw-response recording or native object.

`build_bundle(provider_configuration=..., provider_artifacts=...)` authors an
explicit Provider package using `PROVIDER_EXECUTION_SOURCE_PATHS`, with
`host_binding_provider:create` and a generated, signed `provider_config.py`.
Configuration order does not alter the package. The Artifact input must be the
exact canonical profile/egress/tokenizer/price closure, without unrelated
content or credential fields. Model descriptor and package metadata declare
the same profile; the model Capability is `capability://seed.messages-model`.
The package requires Public API >=1.9 and has no fake adapter in its executable
source set. Supply a new package version when upgrading an existing minimal
installation. The default minimal builder and fake binding are unchanged.

An independent integration fixture starts only the installed Runtime console
with `start --controlled-provider-test-ca <public-CA-file>`. Synthetic credentials
enter the separate installed native provisioning console over stdin. Approval
uses the public signed configuration CLI; tasks use a consumer-owned Actor key.
These tests never import private Runtime modules or inspect its DB/CAS/key files.
They check text, serial tool result history, original-wire billing, unknown
usage, accepted disconnect, missing approval/item and cost refusal before send.
The server is a synthetic loopback fixture with TEST currency and fixture-only
UTF-8 byte counting, not the selected GLM gateway or captured R2.

The normal daemon, production Provider readiness, real exact tokenizer/tariff,
reasoning profile, Managed/EffectIntent gates, release statuses and RP-03 remain
unchanged. See the Runtime contract archive's ADR 058 for the native launcher.

`test_provider_recovery.py` additionally kills actual public daemon processes
after the loopback server receives a request and after a complete terminal
reaches a signed consumer normalizer but before the terminal commit. The latter
uses a deliberately blocking, signed test normalizer with a content-free stdout
marker; production callbacks are unchanged. The accepted-request case observes
prompt TLS peer closure before its ten-second request deadline. After restart,
the same Task/Invocation remains FAILED_RECOVERY/UNKNOWN with its model/effect
counts retained and unknown cost. It is not resent; a new explicitly submitted
Task executes normally with the retained protected credential. These are owned
process/public API observations, not private-store inspection or a sandbox claim.

API 1.10 additionally exposes Fact-checked Provider reservation, settlement and
bounded transport observations through `Task.GetExecution` (ADR 059). The
independent 429 case verifies RESOURCE_EXHAUSTED plus `retry_after_us`, unchanged
single-attempt behavior and unknown cost retaining its maximum liability.
Crash cases inspect the same public liability record and require null transport
metadata when no observation committed. A retry hint never authorizes a resend.

## Durable request lookup/idempotency support matrix

The selected upstream surface (`anthropic-messages-terminal/v1` against the
operator's gateway) declares no durable request lookup and no idempotency key:
the profile fixes a single terminal `POST /messages` exchange with no
status-lookup endpoint and no upstream request identity that a later call could
query. The lookup half of the matrix is therefore `UNSUPPORTED — not
implemented`; no code path claims upstream lookup support it cannot exercise.

The resulting boundary behavior is pinned by named public consumer proofs in
`tests/contract/test_provider_recovery.py`:

- Ambiguous outcome (connection loss after send, owner death, Task deadline
  during an in-flight request, an explicit Task cancellation arriving while
  the request is on the wire): the invocation settles `UNKNOWN` with
  `EXTERNAL_EFFECT_UNKNOWN` and liability equal to the full reservation; the
  Task terminal replays byte-identically after restart. The Task itself ends
  `CANCELLED` for an explicit cancel and the cancel envelope replays its
  durable receipt after an owner restart. The seed loop and Retry
  Policy never automatically re-call the Provider, and a `retry_after_us` hint
  never authorizes a resend of an unknown or settled effect.
- Provably-not-accepted outcome (pre-send failure: no listener, refused before
  any wire byte): the invocation settles `NOT_SENT` with zero liability and
  zero usage; nothing is resent on recovery, and a new explicitly submitted
  Task fails identically while the endpoint is unreachable. Only this provable
  non-admission boundary permits a policy-governed retry, and the current
  profile's policy still requires an explicit new Task submission.

The deadline-during-request case additionally proves a late upstream response
cannot reverse the settled UNKNOWN outcome, the invocation identity or the
replayed Task terminal, and that the retained protected credential keeps
serving new Tasks afterwards. These are synthetic loopback observations; they
do not measure the gateway's real timeout or retry semantics.

Credential containment is proven on the same public surfaces after a real
model+tool run (`test_provider_credential_never_leaves_the_handle_boundary`):
the synthetic fixture secret and its sha256 appear nowhere across the Task
terminal, execution metadata, Fact trace, Harness configuration, acceptance
View, projection-bearing surfaces, manifest, grant requests, every uploaded
Artifact, model/tool outputs and the owned daemon's own stdout/stderr. The
public operator `doctor` scan reports zero findings over every checked blob
and Fact, and the credential appears only as the opaque
`credential://…` handle in the provider configuration. This is a public
API/owned-process observation, not private-store inspection.

The named SH-PROV-03 module (`tests/acceptance/test_live_provider.py`) now
exists as the live job's fail-closed scaffolding. Its gates refuse before any
wire byte: a missing operator authorization file, the committed example's
no-permission defaults, a missing hard request-count/cost-ceiling/timeout
limit, paid fallback, plaintext credential material, or an unresolvable
credential handle. Against a real daemon, a Task without any provider binding
refuses `FAILED_PRECONDITION` and one with an approved-but-unresolvable
handle refuses `KEY_UNAVAILABLE` — both with zero invocations and zero wire
requests observed at the loopback listener. The real controlled live call
remains a separate operator-gated job; the traceability row stays PLANNED
until that evidence exists.

ADR 074 corrects a request-profile bug: application data and JSON Schema
properties named `thinking`, `cache_control` or `server_tool` no longer count
as protocol switches. Actual protocol extensions are still rejected at their
structural positions. The installed development candidate passed 281 Windows
Runtime Provider cases and 279 Linux cases plus two Windows DPAPI-only skips;
independent Seed Provider consumers passed 80 cases on each platform, including
a real Artifact tool followed by a second model request with those ordinary
business fields. This uses synthetic loopback/TEST accounting and adds no
reasoning, cache, server-tool or selected-gateway support. The remaining
reasoning/retention/usage boundary is recorded in
[`provider-reasoning-contract.md`](provider-reasoning-contract.md).

After the operator confirmed quota-only rejection and authorized requests, the
native provisioning entry point imported the specified local configuration's
Provider credential into a separate Windows DPAPI validation store. Only its
opaque handle is retained outside that protected store. No configuration was
rewritten, no secret/recovery code was logged, and no real HTTP/model request
has been sent yet. Billing authorization is resolved; the remaining blocker is
the formal live Host/profile path (exact tokenizer, reasoning continuation and
usage semantics), rather than another request for fee confirmation.

## Native operator wire observation — 2026-11-03

One explicitly authorized diagnostic used the existing Windows DPAPI provider
credential through the native scoped store. It sent at most one non-streaming
request, with a 128-output-token ceiling and 30-second deadline. There was no
retry, redirect, proxy or paid fallback. The diagnostic is separate from the
normal Task/Invocation Host path and does not bypass its admission gates.

Observed: HTTP 200, exact `glm-5.3-flash` model match, ordered `thinking`/`text`
blocks, `end_turn` and final `OK`. Reported input/output usage was 17/17;
cache-read was zero, cache-creation absent, and two additional usage fields
were unrecognized. Their names/values, raw response, reasoning, signatures,
response IDs, origin and credentials were not archived. Cost remains unknown.

Evidence: `reports/provider-wire-observation-v1/wire-survey.json` and its
`verification.json`. This confirms transport reachability and one observed
shape, not exact tokenizer accounting, complete usage mapping, reasoning
continuation, captured R2, product live acceptance, RP-03 closure or release.
