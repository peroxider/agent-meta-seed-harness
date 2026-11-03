# Canonical package inputs and review artifacts

The single package generator is `agent_meta_seed_harness.packaging.build_bundle`.
It creates a signed manifest, Composition, loop policy, scoped grant requests,
model/echo descriptors and build provenance from explicit source/lock/contract
inputs. These are generated together so no checked-in template can drift from
the bytes consumed by Runtime.
`EXECUTION_SOURCE_PATHS` is the shared execution-module allowlist for the CLI
and independent consumer packages. It includes Loop/Context, fake Provider and
PURE echo modules; build/evidence tooling is excluded from execution payloads.
An explicitly supplied loop policy is validated and signed as its own Artifact.

From a built and installed Seed development wheel:

```console
agent-meta-seed build-package . --publisher-key <operator-raw-Ed25519-key> --contract-sha256 <archived-contract-hash> --output dist/package
```

The output contains `manifest.json`, `composition.json`, `loop-policy.json`,
`grant-requests.json`, `capabilities/*.json`, `provenance.json`,
`dependency-lock.txt`, `publisher.ed25519.pub`, `signature.ed25519`,
`package.ampak`, and the complete content-addressed `artifacts/` set.
Named review files are exact copies of their referenced artifacts, not a second
input format. Publisher private bytes are supplied explicitly and never copied
into the bundle. Publishing or trusting a publisher remains an operator action.

The development package implements actual Loop/Context/fake Provider/echo,
not the earlier unbound marker. It requires explicit trusted in-process
placement and does not claim process isolation, paid Provider support or the
complete S02 Context/fault matrix. Release evidence gates remain mandatory.
