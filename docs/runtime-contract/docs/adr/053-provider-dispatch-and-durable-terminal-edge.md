# ADR 053: Bind Provider worker dispatch to durable Host admission

Date: 2026-11-01
Status: internal integrated execution edge; public S04/RP-03 still OPEN

## Decision

`ProviderHostCalls` owns one admitted Provider attempt from authorization through
terminal commit. It uses a Runtime-held Service signer, an actual controller
session and a prevalidated secretless request. Before invoking the worker, the
Host commits `provider-dispatch/v1` in the private invocation journal and an
immutable `provider_dispatch_authorized` invocation Fact. This is authorization
to submit once, not proof that HTTP was accepted or that its outcome is known.

Dispatch reloads the Root/Service public trust from the actual SQLite/CAS
Realm/Epoch and independently verifies the execution token. It binds the
transport request ID, complete request scope hash, maximum output count,
Actor/Action/Realm/Epoch and absolute deadline to the admitted attempt. Both
principals must remain active. The exact grants already used at admission are
revalidated, excluding the use owned by this attempt from each max-use check;
revocation cannot be bypassed by borrowing a newly issued grant. Required
permissions must equal the admitted permission set for each principal. The
daemon's `runtime.token.issue` command guard remains the control-plane boundary.

The dispatch journal projection is checked against its immutable Fact whenever
the Provider accounting record is read. Deleting a mutable dispatch marker does
not permit another submission. Once dispatch is authorized, a new Host/controller
session cannot issue another authorization for that attempt. Confirmed results
replay through the existing Host invocation journal without a native session.
Tokens/signatures, raw worker frames and response bodies are not accounting Facts.

No transaction spans the worker await. The actual worker still independently
verifies its Root-certified token before opening protected credentials and sends
only through the controlled HTTPS edge. A proven NOT_SENT observation settles
zero billed cost. A complete HTTP response is normalized through the selected
bounded codec callback; malformed normalization becomes INVALID_RESULT with
unknown usage and its maximum cost hold. Partial/unknown results never enter a
normalizer. An unclassified port failure after authorization becomes UNKNOWN.

Cancellation waits for the worker's native cleanup, journals the observed result
or uncertainty synchronously, then propagates cancellation before any subsequent
tool effect. A terminal commit failure propagates without a second commit or
another HTTP request. A later Host sees the dispatched, unfinished attempt as
UNKNOWN. A committed usage overrun records its actual amount and raises
RESOURCE_EXHAUSTED before delivering a successful normalized value to the caller.

A pre-dispatch failure can release a hold only if an atomic store check proves
there is no earlier dispatch marker. This prevents a second malformed invocation
from releasing the reservation of an already in-flight first invocation. The
dispatch Fact also detects removal or substitution of that mutable marker.

## Evidence and remaining integration

`tests/unit/test_provider_host.py` combines real SQLite transactions and grant
uses, a Root-signed Service certificate pinned from the store, an actual owned
worker process, protected provider-purpose credentials on Windows and actual
local TLS. Synthetic prices/token counts and normalization are deliberate test
fixtures. Cases include request/credential/deadline/ID/signature substitution,
grant revocation, cancellation after POST, uncertain upstream failure, response
then terminal transaction abort, fresh-connection/controller replay refusal,
confirmed CAS replay, normalization failure, overrun and concurrent malformed
dispatch. These tests do not constitute a full daemon/public-wheel Seed proof.

This edge is not the public Host activity-runner callback: it commits its own
terminal and must not be wrapped in a second generic activity terminal commit.
The public bridge must explicitly integrate this ownership with Task cancellation,
frozen profile selection and the common normalization pipeline.

Profile/credential registration, independent exact-tokenizer and pricing
verification, and EffectIntent/backend admission still precede this edge. In
particular, the native Job/PDEATHSIG mechanisms do not prove Managed strong
isolation or authorize irreversible product effects. Public profile selection,
full daemon/process-kill recovery, independent Seed consumption, captured R2 and
explicitly bounded live execution remain required. No API version, Seed-pinned
wheel, product/platform support claim or RP-03 status is changed by this ADR.
