# Runtime dependency ledger

Initial audit baseline: Runtime source `db9b928`, CPython 3.12 / Windows. This is an input
audit, not a public release compatibility statement. Exact wheel/contract
hashes are recorded in the contract bundle manifest when prepared.

Current development pin: API 1.15, Runtime wheel
`8115d1de814eea5f0e7533f70cfe5977d27eaf7b59e0ef482e2b74efdf424f60`.
The archive includes ADR 063–075. The new native recovery development pin passed
all 1560 Windows unit tests on its frozen input revision. With explicit platform
and deterministic-clock fixture corrections, the same Runtime wheel passed 267
installed checks on each Windows/Linux profile and 39 public-only Seed recovery
checks on each. The latter proves live-Scratch backup refusal, release, public
backup/native restore, retained history, quarantined operations and no heap
adoption. Its fresh installed full Seed regression passed all 393 cases, including
seven native Scratch cases and 28 session document cases, with both non-editable
distributions byte-verified. Evidence: `reports/recovery-v1-installed/reports/installed-bytes.json`.

A later fresh Windows consumer on the same Runtime pin passed all 410 provided
Seed tests with Seed wheel `22afa29f…4236d` (28 Python modules and three JSON
resources). Evidence: `reports/scope-v1-installed/reports/installed-bytes.json`.
This is the independently frozen input snapshot; subsequent CI profile-selector
and test refinements passed 109 focused checks separately. New negative release
gate cases cover S08/S09 scope, cumulative evidence and changed plan inputs;
they do not prove artifact/code evolution. The full goal now includes S08/S09,
whose required implementation/acceptance modules remain missing and PLANNED.

The preceding pin `1a84f6f6…70699` contained the compatible Provider fix and passed 281 installed Runtime
Provider cases on Windows and 279 on Linux with two real Windows DPAPI cases
skipped there; independent Seed Provider consumers passed 80 cases per platform.
Those initial cross-platform checks cover the affected Provider scope. A later
fresh Windows installed full Seed regression passed all 392 cases on this pin,
including six native Scratch cases, 28 session document preparation cases and
the new Provider business-field case. Both distributions were non-editable and
byte-verified. Evidence: `reports/provider-v1-installed/reports/installed-bytes.json`.

The preceding Windows pin `c5a173db…11d7` verified all 1496 unit cases without baseline module
exclusions. Fresh installed profiles passed 381 Windows cases and 380 Linux cases
with one explicitly Windows-only test skipped. The final 33 generic worker cases
include the retained-process-handle assertion strengthened after the all-unit run;
Runtime product bytes are identical across those runs. These are development
functionality proofs, not strong isolation or product release certification.
The preceding retirement pin `db4a588a…23dc4` passed the full independent Seed
consumer: 363 cases, including six native public Scratch cases, with both
distributions non-editable and byte-identical to their wheels. Evidence:
`reports/scratch-v3-installed/reports/installed-bytes.json`.
The changed Windows backend pin also passed all 363 independent Seed cases,
including six native Scratch cases, in the separately frozen
`reports/scratch-v4-installed` environment. Both installed distributions were
non-editable and verified byte-for-byte against the frozen wheels.
This consumer used Seed wheel `5cf5368a…10b70`. Subsequent S06 document
preparation adds one Python module and two schema resources; its separate
installed development check passed 48 cases (28 document cases including two
native public State cases). That preparation is not a full regression of the
new Seed wheel and does not activate sessions. See `docs/session-development.md`.
Historical candidate notes below describe their original, earlier pin state.

| ID | Consumer | State | Missing proof |
|---|---|---|---|
| RP-00 | S01A/S03 | OPEN | Lifecycle, upgrade/drain/uninstall, failed-candidate safety and freshly approved stateless package rollback exist; full fault/state/release matrix remains |
| RP-01 | S01A/S02 | OPEN | Frozen Task/View/Surface and own-key Actor/scoped model/PURE-tool path execute; full Host/Context negative matrix and version publication remain |
| RP-02 | S01A/S02 | OPEN | Public model/PURE-tool confirmed and UNKNOWN process-loss proofs exist; irreversible-effect/terminal/drop-response fault matrix remains |
| RP-03 | S04 | OPEN | Scoped credential injection, egress and cost enforcement |
| RP-04 | S05/S06 | OPEN | Public Artifact/State tools and six Scratch plans execute with child Actions; installed Seed cancellation/kill/restart/drain pass on the changed Windows pin; remaining authority/export/evolution/fault/release matrix remains |
| RP-05 | S06 | OPEN | Public State initialization/audited snapshots/CAS and committed command replay after response loss/kill are covered; session journal/controller, expiry handling and remaining crash coverage remain |
| RP-06 | S07 | OPEN | Task-scoped state trace is available; general Fact/Evidence/Evaluation history and ChangeSet/Candidate/World registration remain |
| RP-07 | S07 | OPEN | Signed promotion binding, ownership and reevaluation |

The operator authorized changes to Runtime on 2026-10-30. Runtime changes
must publish an ADR, contract version and consumer proofs before an OPEN
dependency becomes VERIFIED. A public method name alone is insufficient.

Runtime ADR 031 now implements signature/content/contract validation and ADR
034 implements signed activation guards/delegation with local Runtime proof.
Seed cannot certify S01 until the final pinned wheel has passed the independent
package/lifecycle negative suite.

Runtime ADR 035 publishes Public API 1.1's incarnation-bound `Runtime.Stop`.
The hash-pinned installed-wheel `test_daemon_transport.py` consumer tests pass
real initialization, SDK Hello identity, signed stop, exclusive owner/init and
abrupt process death/restart. This closes the control-plane preparation gap,
not the entire RP-00 dependency.

ADR 037's development Host now binds actual AMPAK instances/health, freezes
admission snapshots and journals zero-cost model/PURE-tool calls. The installed
wheel `tests/acceptance/test_host_bootstrap.py` builds an independent signed Seed
package, uploads/installs/activates it through public CLI, verifies complete
normalized terminal/echo/two-tool/free-text/LENGTH behavior via public SDK,
kills a real daemon with a dispatched model call, observes FAILED_RECOVERY
without another invocation, then executes after restart and deactivates/uninstalls.
It never reads Runtime DB/CAS/keys/source. This is bounded development evidence;
the full S01A/S02 matrix, supported Host contract version, upgrade fault suite
and release gates still block verification. Details are in `docs/host-integration.md`.

ADR 038 adds full-package Python source/API-boundary checks, exact provenance
file/hash claims, package code ownership and scoped-grant validation. The named
S01 command `test_package_contract.py` now combines reproducible build/path
proofs with actual public-wheel golden/negative validation, entrypoint
non-execution, equivalent install, signed-policy name/version conflict and
uninstall-history tests. Negative cases are independently declared in
`tests/fixtures/package/negative-cases.json`.

Runtime-owned real-AMPAK proofs also exercise failed upgrade preservation and
old-serving execution before/after owner restart. Its readiness uses actual
serving health rather than the desired candidate status. The assembled Host
now supplies its own profile hash and reports unattached Backend features as
UNSUPPORTED; it cannot inherit Portable worker capabilities merely from a
static feature table. Strong Backend and full independent upgrade/fault proofs
remain OPEN.

ADR 039 now implements frozen Context source capture, artifact-bound policy and
normalizers, exact declared tokenizer/renderer resources and Host recomputation.
Seed uses the public mechanism and its fake Provider consumes projected input.
Runtime tests cover redaction, the quota ladder, 100 replays and forged requests;
the public-wheel daemon also checks exact redacted output. Full independent
Context provenance/fault proofs and the Host version gate remain OPEN.

ADR 040 publishes Public API 1.2 `Task.GetExecution` / public SDK
`get_task_execution(task_id)` / CLI `task execution <id>`. It returns bounded
Task/Invocation/Projection and accepted/consumed budget metadata through the
authenticated local operator channel. The named `test_host_recovery.py` and
`test_loop_recovery.py` now kill actual daemon owners only after public metadata
confirms the requested durable boundary. Independent consumer callback markers
and random normalized content distinguish a replay from a second Provider/tool
call. Confirmed outputs/history and budgets survive without redispatch; in-flight
UNKNOWN stops as FAILED_RECOVERY. These development proofs retain OPEN status
until the remaining fault, Host-contract and release matrix is complete.

ADR 041 corrects uninstall guards to the target installation's typed ownership
closure and retires all superseded activation-grant generations. The public-wheel
`test_release_lifecycle.py` now upgrades an actual independent package while a
confirmed old Task drains, uninstalls that old version while the new one serves,
and checks a failed candidate preserves serving. A separate case proves an old
Task's subsequent tool call cannot borrow the new installation's or Root grants
after scoped-grant revocation. State owners and unsettled/UNKNOWN Effects remain
uninstall pins. These are bounded development proofs, not release verification.

ADR 042 publishes Public API 1.3 `Artifact.GetContent`, SDK
`get_artifact_content(artifact_id)` and CLI `artifact content <id>`. Independent
installed-wheel tests compare empty/binary/1 MiB content, reject larger/missing
objects and check read-only behavior. Context proofs now fetch actual stored
manifest/section/rendered bytes and independently compare hashes/counts; the
bootstrap proof reads complete normalized terminal bytes. Restricted reads,
Host-scoped Artifact tools, State/Scratch and the rest of RP-04 remain OPEN.

ADR 043 corrects strict Task submission scalars and deadline-zero handling,
and exposes the existing deadline field in CLI. The independent Host contract
suite now observes queue expiry, active timeout/cancel, confirmed-output
preservation and immutable consumption after terminal. Schema/JSON rejection
occurs through public CLI with stable parameter errors. Broader principal/epoch,
fault/replay, Backend and release cases still prevent RP-01/RP-02 verification.

ADR 050 adds a selectable actual InMemory Host with Root-certified Service
tokens, real handles, durable Invocation terminal/ack intent and public API 1.6
binding/profile inspection. Named AC-M17 now completes Seed's own context →
fake model → echo → execution Facts → why → completion path. The independent
model/tool recovery suites also kill actual processes under this selection and
preserve confirmed outcomes without redispatch, stopping UNKNOWN outcomes.
Ack response loss and unavailable old sessions are explicitly observed. These
Windows development proofs retain OPEN dependency status; they do not establish
strong isolation, a complete fault matrix or final release/CI compatibility.

### API 1.13 Scratch candidate (2026-11-03; not pinned)

Runtime ADR 068 adds candidate public imports
`agent_meta_runtime.sdk.host.ScratchCreate`, `ScratchExecution`, and
`ScratchRelease`, consumed through the existing pure `ResourceAdapter` and
asynchronous Root Host. The resource contracts are `scratch.create/v1`,
`scratch.execute/v1`, and `scratch.release/v1`. Creation requires both
`scratch.create` and `scratch.execute`; all operations additionally require
Capability invocation and actual resource scope for Actor and Harness Service.
Execution reads an explicitly authorized Source Artifact and returns bounded,
policy-redacted output Artifact references. These are trusted exploration
operations, not an adversarial sandbox.

The candidate Runtime wheel hash is
`eabb277485d5ecc37565f7443dcfe2c8f06a85073b9330db2791e083aa44a76a`.
Its independent installed Runtime-owned signed-package suite exercises actual
kernel creation/execution/release, cancellation, redaction/truncation, failed
normalization and confirmed replay on Windows/Linux. This is not Seed consumer
proof. The candidate does not yet expose bindings/inspect or Candidate export;
its binding-name change metadata is explicitly conservative.

Seed's Runtime wheel, contract archive and `requirements-ci.lock` remain on the
verified API 1.12 pin `b719c416e36076c9e3f054304e87361e53d6931eee41f739ce93b45a8c600a7c`.
RP-04/S05 remain OPEN. Before adding Scratch to Seed's advertised tool catalog,
update the explicit wheel/contract pin, implement the public-only Seed adapters
and descriptors, and run installed Seed consumers and required fault/export
cases. Existing certificates limited to model/capability invocation also need
explicit provisioning for Scratch; a new certificate alone never grants scoped
operation authority.

### API 1.14 Scratch observation candidate (2026-11-03; not pinned)

Runtime ADR 069 adds public `sdk.host.ScratchBindings` and `ScratchInspect`
plans, both PURE with effect `none` and scoped `scratch.inspect` permission.
Actual tool-step accounting, Actor/Service grants, certificate bounds and frozen
operation/session checks still apply. Root derives binding Source/Action origins
from admitted cell Facts. Inspection accepts one identifier or previously issued
weak handle and never submits an evaluation cell. Public reflection uses
`handle`; credential `token` fields and sensitive child labels remain redacted.

The candidate wheel is
`fb37c9f924c49568b990f4780cc39a01a9d2d1cc3a562dc95ad145b20c164cb8`.
Its fresh Windows/Linux non-editable environments each passed 334 Runtime-owned
tests, including 17 signed-package Scratch cases. Both installations verified
all 177 Runtime Python files against the same wheel. These are Runtime proofs;
they do not establish installed Seed consumption. Main-thread name-write
tracking is limited to CPython 3.12; heap mutation remains `UNKNOWN_RISK` and
incompleteness/truncation is explicit. Weak-handle expiry is audited.

Source-only public export, the complete Scratch toolset, RP-04 and S05 remain
OPEN. Seed's published pin and contract archive stay on API 1.12 until the
explicit archive/pin update and public-only consumer validation are complete.
