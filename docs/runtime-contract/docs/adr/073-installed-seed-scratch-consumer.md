# ADR 073: Installed independent Seed Scratch consumer

Status: Verified development cohort, not a release or completion of S05/RP-04.

The external Seed repository now consumes all six public Scratch plans through
pure ResourceAdapter callbacks, signed descriptors and scoped Capability/input
Artifact-kind grants. Its source imports only public SDK modules. The native
worker and all storage, authorization, policy, publication and retirement remain
Root responsibilities. Minimal/fake and Provider-tools bindings retain the same
typed dispatcher and serial order.

The explicit API 1.15 development pin is Runtime wheel
`db4a588ae51fe5e9dbee14630c04cf8f4f369dacfb80f71ab418cee842923dc4`.
Root verified 1463 selected unit tests and 348 fresh installed tests on each of
Windows and Linux. Its optional kernel stack is hash-locked. The contract archive
includes ADR 063–071, with a preserved copy of the prior Source-export pin.

Seed wheel
`5cf5368a340b16945ac679e65cf42b01f54f0b1f654b99141fc9511c5e410b70`
passed all 363 tests in a fresh Windows environment with both wheels installed
non-editable. Verification compares every installed Runtime Python file (179)
and Seed file (26) with the exact wheels. Six independent native Scratch cases
cover the full tool sequence, typed inspection rejection, cancellation with an
entered binding still safely observable, daemon kill/restart with expired weak
handles and no heap adoption, and retirement before READY followed by successful
reactivation with new empty Realm capacity. These consumers use public SDK/CLI,
never Runtime stores, private fixtures, database rows or workspace files.

The first isolated full run omitted its explicit dist input and retained one
missing-file failure. The corrected fresh run preserves wheel/sdist/SBOM/
provenance, passes that coherence check and the entire suite. Those reports remain
distinct. An earlier Source-export cohort independently passed 362 tests with
the previous wheel; it is not evidence for the new retirement behavior.

Evidence: `reports/scratch-drain-v1-input/runtime-seed-verification.json`, joined
from the Root checkpoint and Seed's
`reports/scratch-v3-installed/reports/installed-bytes.json`. A narrative grammar
correction after input freeze is explicitly recorded; executable, test, contract,
authorization and build inputs stayed fixed throughout the consumer run.

Full S05/RP-04 still requires its remaining fault/authority/evolution matrix and
prerequisite gates. S04 real-model codec/tokenizer/accounting and captured traffic,
S06 conversations, S07 evolution, strong World constraints and actual release/CI
approval remain separate. The user's real-provider authorization permits existing
subscription/free quota only, with zero incremental cost and no paid fallback;
no external model call was made. The newer generic Windows Backend work is a
separate unpublished candidate and is not included in this pin or these counts.
