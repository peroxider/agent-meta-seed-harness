# Release evidence and candidate preparation

This is the S03 evidence contract. No product profile or Runtime dependency is
currently VERIFIED. `tests/contract/test_release_evidence.py` is development
evidence of real artifact coherence; synthetic unit fixtures test the verifier
only and are never acceptance evidence.

The Runtime input is an explicitly supplied wheel. `release_inputs` verifies
its actual distribution identity, every binary wheel/hash against the complete
lock, exact project pin, CI platform identity, and every archived contract file.
It reads only this Seed snapshot and its declared artifacts. No neighboring
Runtime source, private Runtime import or mutable readiness fixture is used.

A requirement's `evidence` has hash references `{path, sha256}` for `junit`,
`environment`, `runtime_wheel`, `contract_bundle`, plus `test_hashes` for every
named proof. `artifacts` contains references for `seed_wheel`, `seed_sdist`,
`seed_sbom`, `seed_provenance`, and `package_bundle` (the bundle.json marker).
Paths are relative POSIX paths inside the evidence root. JSON duplicates,
escaping paths, oversized JSON/JUnit, unidentified/duplicate tests and any
failure/error/skip/xfail are refused.

Release environments use `schema=seed-consumer-evidence/v1`, `status=VERIFIED`,
the cumulative `profile`, full `seed_commit`, all fields from `release_inputs`,
all identities from `verify_candidate_artifacts`, `junit_sha256`, the actual
isolated `command`, sorted `execution_profiles`, `credential_profile` and
`contracts={public_api,harness,capability,artifact_format}`. Reports must bind
the exact final source, fixtures, lock, policy, Runtime wheel and contract.
The source digest recipe hashes executable/test/script/package/CI files and
the project, lock and reviewed publisher policy; reports and mutable status
ledgers are excluded to avoid circular evidence hashes.

The verifier checks real Seed wheel metadata/source bytes, sdist source/lock/CI
and policy bytes, every SBOM component/hash, build provenance and the complete
signed AMPAK closure. AMPAK source and dependency lock must match the same final
snapshot. Environment identities include both distributions, SBOM/provenance,
bundle/manifest/package IDs and publisher public-key fingerprint. A build's
`DEVELOPMENT_NOT_RELEASED` provenance identifies candidate bytes; only separate
reviewed consumer evidence can establish test verification. It is not a release
verdict or publication authorization.

`docs/release-policy.json` contains the reviewed `approved_publishers` list.
It starts empty; public test keys are not approved for product release. Package
generation may consume an operator-provided signer, but the verifier opens only
public bundle data. Private signing material must stay outside distributions,
AMPAK, reports and this policy. Updating policy changes the source/input binding
and requires fresh evidence.

Each dependency references a `seed-runtime-dependency-proof/v1` document with
`dependency`, `status=VERIFIED`, exact `runtime_wheel_sha256`/`contract_sha256`,
the fixed `requirements` list from `DEPENDENCY_REQUIREMENTS`, and a complete
`consumer_evidence` object of the same shape as a requirement proof. Required
modules must actually be collected and hashed; all relevant requirement rows
must also be verified. Dependency and requirement reports must describe the
same final inputs, commit, publisher, contracts, credential and Backend profile.
This binding is necessary and does not replace review of assertion coverage.

Development evidence uses `seed-development-evidence/v1` and DEVELOPMENT_ONLY.
The recorder verifies the complete current pytest collection, the actual
persisted candidate, input hashes and observed public InMemory/trusted profile
cases. Windows DPAPI and non-Windows INSECURE_TEST_ONLY results remain distinct.
These reports are refused by the release environment validator.
Collection ignores inherited pytest filters/JUnit options so it cannot accept
a narrowed run as complete or overwrite the report being checked. Negative
ledger tests use explicit unverified copies; they do not require the real
project to remain unverified after its legitimate release gates are satisfied.

After every required consumer/platform gate and dependency is actually
verified, run `python scripts/build_release.py --profile minimal`. It writes
`dist/release/minimal/candidate.json` with READY_FOR_OPERATOR_REVIEW, preserving
the exact tested artifact/evidence references. Different existing output is
refused; an identical rerun is idempotent. It performs no rebuild, signing,
publishing or activation. CI release report production, multi-platform support
aggregation and actual authorized publication remain separate unfinished work.

## Owned prebuilt-bundle consumer runs

`scripts/run_consumer.py --bundle BUNDLE_JSON --label NEW_LABEL --profile minimal`
validates supplied signatures, stages only the public Artifact closure, seals
source/lock/distribution inputs, and owns the full isolated pytest command.
Default package consumers use that exact supplied bundle; explicitly customized
negative fixtures retain their independent test signer. Missing, tampered or
stale prebuilt input never falls back to rebuilding a test package.

AC-M17 observes the actual public transport handshake, Runtime validation's
resolved contracts, selected backend profile, init credential classification,
and installed package/manifest/publisher identities. Its observation carries
the owned run ID. The producer requires the post-run snapshot and exact tested
artifact identities to match its pre-run seal, then writes environment/proof
and a PENDING_COVERAGE_REVIEW index. Requirement/dependency statuses are never
changed by the producer. Invalid evidence receives a terminal failure state.

Development mode emits DEVELOPMENT_ONLY. Explicit `--kind release` additionally
requires a clean committed source/input snapshot, matching identifiable GitHub
CI context, an approved publisher, and actual protected Windows credentials.
Only that verified execution record uses the release environment schema; it
still does not prove assertion coverage or close any ledger row. Non-Windows
insecure test profiles fail release preflight. No release-kind run has been
claimed for the current uncommitted development snapshot.

The preparation input requirements-ci.in is included in the source digest and
sdist along with the exact installation lock. A source/lock/preparation-policy
change therefore invalidates existing evidence before any candidate decision.

## CI handoff

The Windows `ci.yml` workflow downloads the explicit Runtime wheel and the
committed hash-locked dependencies in its preparation job. It does not update
the lock. The verification job separately downloads a public `seed-package-bundle`
artifact from the specified repository/run. That artifact must contain
`bundle.json` and its `artifacts/` closure, with signatures and execution inputs
matching the checkout. No signer or private key is supplied to the consumer job.

The offline job builds the distribution, SBOM and provenance before installing
the wheel and invoking `run_consumer.py`. It uploads `reports/ci-consumer/` and
the exact tested `dist/` under `seed-consumer-evidence`; it performs no post-test
rebuild. Python outbound rules cover both the venv redirector and base
interpreter. The workflow pins the Python patch version declared by the current
Windows inputs. Updating that input requires explicit lock/profile review.

`evidence_kind` defaults to development. Choosing release invokes all producer
preconditions, including approved publisher policy and clean committed CI
identity; it does not approve coverage, close the ledger or publish a package.
`release.yml` consumes this same artifact name and remains subject to the
independent release gate. The YAML and embedded PowerShell have been parsed
locally, and the build/installed-wheel/owned-consumer commands run locally.
No hosted Actions run, firewall enforcement result, Linux CI job or product
release is claimed by those checks. Linux development runs remain separate
and use explicitly insecure test credentials.
