# ADR 034: Signed activation plans and installation-owned delegation

Date: 2026-10-30
Status: accepted; public-wheel Host/reconcile release proofs remain open

## Decision

Enforce the existing §41.60.4 activation preconditions without adding an RPC or
changing Public API v1 message fields. `harness.activate/v1` requires:

- `plan_hash`: the exact `Harness.ValidatePackage` report's plan hash, binding
  signed manifest content, selected contracts, Backend profile and trust result.
- `grant_request_hash`: lowercase SHA-256 of JCS of the exact signed request
  array. The request array itself must equal the publisher-signed manifest's
  referenced Grant request array.
- `expected_meta_revision` in the CommandEnvelope and
  `expected_serving_revision` in its signed payload. Missing guards are errors;
  a changed revision rejects the command instead of silently refreshing a plan.
- Exact Composition body Artifact identity in the signed payload. The actual
  body is validated independently of the package template before mutation.

The SDK's `prepare_harness_activation` reads the installation and validation
report, obtains one public View for missing revision guards, and returns the
full canonical signed command without submitting it. Explicit hashes/revisions
are preserved. `activate_harness` submits that prepared representation. The
CLI dry-run displays these same hashes, guards, requested permissions and exact
command representation; the normal path submits the representation once.

An activation requires an operator Root signature. Merely possessing
`harness.activate` does not confer authority to issue another permission.
Activation creates its scoped Grants through the existing Authority delegation
mutator, including current epoch, status, time, uses, depth, permission and
scope containment. Child Grants name the actual issuing Principal and parent
Grant and are nondelegable. A reviewed batch under one signed command reserves
one parent `delegate` use; the public command admission separately reserves one
`command` use. Both reservations and every child definition/history/Fact commit
in the activation transaction; denial rolls them all back.

Root bootstrap must use its Realm's actual current epoch. Delegation may not
use an old-epoch or expired parent merely because its stored status is ACTIVE.

The Composition catalog contains only descriptors declared by this installation
plus explicit Runtime builtin descriptors from the composition root. A matching
global registration from another installation does not confer ownership.
Each slot must bind its descriptor's exact code Artifact. The compatibility
solver checks the actual slots/wiring/placement/features/permissions. Grant
request Realm and Capability targets must also belong to that activation.
Missing or ambiguous active Runtime Service identity fails closed.

Committed replay verifies identity and returns the original receipt and
resource before mutable validation/revision/grant state. It does not recreate
Composition revisions, scoped Grants or reconcile outbox items.

## Evidence and limits

`tests/unit/test_activation_authority.py` exercises the real local IPC/SDK path
with signed AMPAK fixtures, a nonempty Composition and a two-Grant batch. Its
negative cases cover altered hashes, missing/stale guards, foreign Realm,
registered foreign Capability, substituted code, non-Root actor, missing
delegation permission and inability to issue the requested permission. It
checks that denied activations create no Composition, Grant, use, history or
outbox records. Existing lifecycle and Authority regressions remain required.

These are Runtime unit/integration proofs. They do not prove Backend health,
serving cutover, bound Task Host, process restart recovery or an independently
installed external consumer lifecycle. Those gates remain open, and this ADR
does not promote a Seed release profile or change Harness Contract 1.1.0.
