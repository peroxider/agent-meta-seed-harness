# Minimal Seed development and release runbook

Current scope is an explicitly trusted publisher, offline fake Model Provider,
PURE echo, cooperative cancellation, and the truthful InMemory development
profile. No product compatibility row is verified yet. Commands below use
public CLI/SDK only. Root/Service signing keys are handled by Runtime; Seed
does not read their paths or material. Application Actors use their own keys
and public attenuated grants as demonstrated in `tests/seed_actor.py`.

## Prepare and review the exact input

Use CPython 3.12 and the appropriate platform-specific binary lock. Supply an
explicit Runtime wheel/hash and archived public contract as described in the
README. Install offline from the hash lock, build the Seed distribution, and
install its wheel in the consumer environment. No editable dependency or
neighboring Runtime source is permitted. Keep `requirements-ci.in` with the
source archive; `requirements-ci.lock` is the actual installation input.

Build an AMPAK with the public `agent-meta-seed build-package` command. Its
`--publisher-key` is an operator-provided Seed publisher key outside the source,
output, reports and Runtime key store. Do not use the public test publisher for
a product release. The package CLI takes the SHA-256 of the archived contract
manifest, not a guessed version string. Review `bundle.json`, `manifest.json`,
`composition.json`, grants, Loop policy, source provenance and public publisher
fingerprint. `docs/release-policy.json` must contain the independently reviewed
publisher fingerprint before release evidence can be generated.

The current development version mapping is 0.1.0.dev1 / 0.1.0-dev.1. A new
release requires a new distribution/package version and matching builders;
do not replace an installed name/version with different bytes. The public
`build_bundle(version=...)` API and lifecycle suite demonstrate versioned
AMPAK upgrades; complete distribution version automation is still pending.

Run the complete consumer job against the final signed bundle:

```console
python scripts/run_consumer.py --profile minimal --kind development --label candidate-run --bundle package/bundle.json
```

Use a fresh label each time. The runner owns the pytest command, freezes input
hashes, installs the supplied bundle through the consumer tests, and compares
the actual Runtime observation with its exact package/manifest/publisher IDs.
It never reads a signer or silently replaces an invalid input with a test
package. Custom negative fixtures remain separately signed test packages.
Review `run.json`, `environment.json`, `proof.json`, `coverage-index.json`,
`runtime-observation.json` and JUnit under `reports/<label>/`.

`--kind release` additionally requires a clean committed snapshot, matching
identifiable CI run, approved publisher and protected credential observation.
It verifies the execution report; it does not mark any requirement or Runtime
dependency VERIFIED, publish, or activate. Current non-Windows development
runs explicitly use INSECURE_TEST_ONLY and cannot produce release evidence.

## Initialize and serve

In the operator's shell, set the data directory explicitly on every command:

```console
agent-meta --data-dir DATA --output json init
agent-meta --data-dir DATA --output json start --execution-backend in_memory --trusted-publisher PUBLISHER_SHA256
```

`start` stays in the foreground. Use another shell for management. Secure
Windows initialization uses CurrentUser DPAPI and owner-only paths. The explicit
`--insecure-dev-credential-file` flag is for isolated non-Windows test data only;
it is never a fallback for missing product credentials. Keep the recovery code
outside logs/reports. A fresh core-ready Runtime has no serving Harness yet.

## Upload, install, inspect, activate

Upload the exact content-addressed files listed by bundle.json, using public
`artifact put FILE --kind code --media-type application/octet-stream`. Require
each returned ArtifactId to match the bundle's hash before continuing. Upload
only the declared public Artifact closure, never a publisher key file.

```console
agent-meta --data-dir DATA --output json harness validate MANIFEST_ARTIFACT_ID
agent-meta --data-dir DATA --output json harness install --name agent-meta-seed-harness --version PACKAGE_VERSION MANIFEST_ARTIFACT_ID PACKAGE_ARTIFACT_ID
agent-meta --data-dir DATA --output json harness inspect HARNESS_ID
```

Review the resolved contracts, trust, requested permissions and backend
features. Validate/Install must not execute the package adapter. Review each
grant request and composition before explicit activation. Repeat `--grant`
once per exact JSON request from grant-requests.json; preserve the scope and
constraints. Do not replace scoped requests with Realm-wide grants.

```console
agent-meta --data-dir DATA --output json harness activate HARNESS_ID COMPOSITION_ARTIFACT_ID --grant GRANT_REQUEST_JSON
agent-meta --data-dir DATA --output json refs
agent-meta --data-dir DATA --output json info
```

Wait for actual serving readiness and the expected serving revision. A persisted
revision or healthy factory alone is not execution evidence. The SDK's current
`get_view(include_backend=True)` reports the selected profile hash/features.

## Task, evidence, cancellation and recovery

Upload a JSON input such as `{"provider":"fake","scenario":"echo","value":"hello"}`
with `artifact put FILE --kind task_input`. Submit with an ordinary Actor's
signed public SDK authority for application use. The following operator CLI
commands are useful for a controlled administration smoke test:

```console
agent-meta --data-dir DATA --output json task submit --input-artifact INPUT_ARTIFACT_ID
agent-meta --data-dir DATA --output json task wait TASK_ID --timeout 30
agent-meta --data-dir DATA --output json task execution TASK_ID
agent-meta --data-dir DATA --output json task trace TASK_ID
agent-meta --data-dir DATA --output json why TASK_ID
agent-meta --data-dir DATA --output json artifact content RESULT_ARTIFACT_ID
agent-meta --data-dir DATA --output json task cancel TASK_ID --reason operator_cancel
```

Retain the TaskId and original command identity. Use execution/trace/why to
correlate frozen View/Surface/Projection, model/tool Invocations, actual Backend
binding hashes and terminal acknowledgement. Content reads are bounded ordinary
Artifact reads. Restricted data is not recovered through a plaintext fallback.

After owner loss, restart the same data directory with the same selected
profile/trusted publisher. Confirmed results and counters replay from Meta Store
without another callback. UNKNOWN / FAILED_RECOVERY is not permission to submit
the same effect again. Preserve its evidence for explicit recovery. A lost
ephemeral InMemory session can leave `UNAVAILABLE_SESSION_LOST` acknowledgement
metadata while the already confirmed normalized result remains authoritative.

## Upgrade, drain, deactivate and uninstall

Build/upload/install a new immutable version and validate it before activation.
Record the current refs and use `--expected-revision` / `--expected-serving` on
activation to guard the intended cutover. Wait for actual reconcile readiness.
A bad candidate must leave the old healthy serving version operational.
Old confirmed work may drain; old Tasks cannot borrow the new installation's
grants for subsequent effects. Inspect remaining Task/State/UNKNOWN references
before uninstalling the old package. Do not edit database refs to bypass pins.

To return to a still-installed old stateless package, validate it and approve a
fresh activation with current meta/serving guards. This creates a new immutable
Composition revision and fresh scoped grants; it does not revive revoked old
grants. Preserve the signed command bytes before submission. If the response is
lost, replay those exact bytes through public `execute_command` after reconnect
or restart rather than preparing another activation. The lifecycle suite proves
the original response bytes and revision/grant IDs are returned without a
second activation. This operation does not restore managed State or undo
external effects; generic Composition/State rollback requires separate proof.

```console
agent-meta --data-dir DATA --output json harness deactivate HARNESS_ID
agent-meta --data-dir DATA --output json harness uninstall HARNESS_ID
agent-meta --data-dir DATA --output json stop
```

Uninstall can legitimately be refused while references remain. Stop targets the
authenticated daemon incarnation. The upgrade/drain/failure and process-loss
consumer suites are runnable examples; rollback and the remaining full fault
matrix are still pending, so this runbook makes no completed release claim.

## Release decision

Review assertion coverage before attaching proofs or closing RP dependencies.
`check_seed_traceability.py --profile minimal` must refuse missing/unverified
evidence. Only after all real profile/platform/dependency gates pass should
`build_release.py --profile minimal` prepare the exact tested candidate manifest.
It performs no rebuild, signing, publication or activation. Keep Seed's release
decision independent from Runtime's release conclusion. S04–S09 add their own
Provider, tool, session, configuration/artifact/code evolution operations and
proof requirements. Both CI workflows offer the same cumulative profile list;
the owned consumer forwards the selected profile and refuses missing named
modules before loading a bundle or starting Tasks. A selectable profile is not
a product support declaration.
