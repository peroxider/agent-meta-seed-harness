# ADR 054: Public Provider plan and normalization callbacks

Date: 2026-11-01
Status: additive SDK/API 1.7 SPI; configured Provider execution remains OPEN

## Decision

Public API minor 7 adds `ProviderAdapter`, `ProviderRequestPlan` and
`ProviderTerminalResponse` under `agent_meta_runtime.sdk.host`. Wire field
numbers and existing RPCs are unchanged. The Harness/package contract stays
1.1, and existing four-argument adapters retain their behavior. The resolved
public API contract version and Hello maximum minor are updated together.

A Harness selects either its existing asynchronous `invoke_model` callback or
the new Provider callback pair. Configuring both is invalid; an unavailable
Provider never silently falls back to a fake or alternate model callback:

```python
HarnessAdapter(run_task, None, tools, probe,
               provider=ProviderAdapter(prepare_request, normalize_response))
```

Both Provider callbacks are synchronous. `prepare_request(ModelInvocation)`
returns a frozen `ProviderRequestPlan(profile_artifact_id, body)`. The terminal
Messages body is canonical bounded JSON with an explicit model, message array,
positive output ceiling and `stream=False`. Transport headers, endpoints and
credential handles are not plan fields. Runtime independently selects these
from an operator-approved frozen binding; a requested profile reference is not
approval or a permission grant. Other wire protocols require a subsequent
explicit contract extension.

`normalize_response(ProviderTerminalResponse)` receives only the selected profile
ArtifactId and one complete bounded body. It returns the same normalized
`ModelResponse` used by the legacy/fake path. No transport, worker, credential,
HTTP headers, signer, store or native backend object crosses this boundary.
An asynchronous/malformed plan, failed callback or invalid normalized response
is INVALID_RESULT; callback diagnostics are not public results. The common
ContentPart, schema, serial tool ordering, ID uniqueness, cancellation and
terminal validation rules remain in force.

The internal Root `ProviderModelHost` port performs profile/tokenizer/pricing
preflight before `HostExecutionStore.reserve`. Prepared requests and reservation
identities must match. The Provider journal input is `host-model-request/v2`,
which adds the selected profile reference and canonical body hash to the frozen
projection/history identity. Existing fake inputs remain v1. On success the
Provider execution edge owns terminal commit; TaskSession must not wrap it in
the generic activity runner and commit another terminal.

An enforcing implementation must independently derive usage and cost from the
controlled response and frozen pricing, rather than trusting a package's
normalized cost claim. It must verify an exact tokenizer for the chosen model
and projection, firm maximum cost, activation/profile/credential binding,
EffectIntent/backend policy and actual worker placement. No transaction spans
the external await. Cancellation is checked again before admission and before
any normalized response can advance the tool dispatcher.

## Current executable boundary and evidence

The daemon has no configured Provider admission implementation yet. A valid
public plan therefore fails with FAILED_PRECONDITION before an Invocation,
host-invocation grant use, model-call/effect reservation or worker dispatch.
The current trusted/in-memory backend profiles continue to advertise their
actual zero-cost execution policy. Importability and API minor negotiation do
not advertise an operational or paid Provider feature.

Public DTO tests check immutability, bounded/canonical bodies, closed terminal
request fields, transport/credential/stream rejection and callback exclusivity.
`tests/unit/test_public_provider_host.py` runs an actually signed/installed
package and accepted Task through local IPC under both current Host profiles.
It proves valid unavailable plans and malformed/asynchronous callbacks fail
before any Invocation, use/reservation or execution binding. It is a public
failure-path proof, not a configured Provider success or complete RP-03 proof.

The operator approval/data primitive is described in
[ADR 055](055-provider-profile-approval-and-frozen-pricing.md). Protected credential
provisioning, the configuration-aware execution registry/bridge,
exact-tokenizer implementation, pricing/usage enforcement in the real execution path,
profile-aware Context and capability surface, and configured daemon-to-worker
success/restart/cancellation/commit proofs remain required. The Seed-pinned
Runtime wheel is unchanged. S04/RP-03, captured R2 and bounded live execution
remain OPEN; no credential or live request is used for this SPI change.
