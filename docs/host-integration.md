# Public Host integration status

Status: IN_PROGRESS. RP-00–RP-02 remain OPEN.

The lifecycle suite now also returns to an installed old package through a
freshly signed activation, with a new Composition and new grant generation.
It rejects a stale signed plan, discards the actual committed activation
response at the public transport edge, restarts the real owner, and compares
the byte-identical replayed response twice. Previously confirmed Task records
remain unchanged, new Tasks execute the old version again, and an uninstalled
version cannot be reactivated. Both trusted_in_process and actual InMemory
profiles are exercised. This is stateless Harness lifecycle rollback; it does
not certify generic Composition rollback or RESTORE_PARENT State restoration.

The explicit Runtime development wheel exposes Public API 1.6 and Harness
Contract 1.1.0. ADR 037 adds a development bound trusted in-process Host;
there is no released Host compatibility claim yet. Exact wheel and contract
hashes live in `docs/ci-inputs.json` and `docs/runtime-contract/manifest.json`.

## Control plane available for consumer verification

On Windows the following commands use native Named Pipes, OS peer identity,
CurrentUser DPAPI and protected credential DACLs:

```console
agent-meta --data-dir C:\runtime-data --output json init
agent-meta --data-dir C:\runtime-data --output json start
agent-meta --data-dir C:\runtime-data --output json info
agent-meta --data-dir C:\runtime-data --output json stop
```

`start` runs in the foreground; use another shell for `info`/`stop`. An empty
bootstrap reports core-ready and serving-not-ready. `connect(data_dir)` opens
the public SDK's local transport. `client.server_instance_id` comes from the
authenticated Hello exchange. Administrative commands are signed by the public
CLI through Runtime's credential adapter; Seed never reads a key/DB/CAS path.
Adapter execution must never inherit operator Root authority.

`tests/contract/test_daemon_transport.py` invokes the published console entry
point under the installed wheel's isolated interpreter, from an unrelated
working directory. It checks real SDK discovery, signed stop, exclusive owner,
abrupt death/restart and fresh incarnation identity. This is control-plane
consumer evidence only. No readiness boolean or Task state is advanced by a
test fixture. Non-Windows runs explicitly select INSECURE_TEST_ONLY storage and
cannot establish a product security profile.

The offline test guard permits only the standard library's scoped socketpair
creation needed by Windows asyncio. Ordinary loopback and Internet connect /
connect_ex remain blocked; this does not change the Named Pipe transport.

## Development execution path

The signed AMPAK entrypoint is `agent_meta_seed_harness.host_binding:create`,
a synchronous zero-argument factory returning the public HarnessAdapter.
Health receives no fabricated Task. Seed's Loop, Context, explicit fake Provider
and echo use only the published facade. Runtime commits all durable records.
The entrypoint binds `loop.py`, `context.py`, `providers/fake.py` and
`capabilities/echo.py`. The Loop validates the signed policy and bounds its
model turns by both that policy and the accepted Task budget. Runtime still
authorizes and reserves every call independently. Package CLI and consumer
fixtures share one explicit execution-source allowlist.

`tests/acceptance/test_host_bootstrap.py` runs from installed wheels against a
separate real daemon process and the independently built Seed AMPAK. It verifies
actual health/readiness, full multipart results, serial echo/two-tool dispatch,
free-text non-dispatch, LENGTH, process-kill UNKNOWN recovery, restart execution,
deactivation and uninstall. Public causal queries check invocation counts;
terminal ArtifactIds match exact normalized expected bytes. No Runtime private
implementation, readiness fixture or storage inspection participates.

The package contract suite also exercises public validation negatives and
Validate/Install non-execution from the named S01 test module. ADR 038's source
audit is an API-boundary check, not Python isolation. Runtime-owned upgrade
tests prove old-serving continuity and restart after a failed candidate;
independent successful-upgrade/drain proofs are described below; rollback and
the remaining lifecycle fault matrix are still required.

The current profile requires an explicitly trusted publisher, supports only
zero-cost model results/PURE tools and uses `utf8-bytes/v1` for Context. It does
not establish process isolation, controlled Provider egress, public State reads
or the complete fault matrix. The package contains an
explicit `fake` Provider, with `terminal`, `echo`, `two_echo`, `free_text`,
`length` and cooperative `wait` workloads; it never silently selects a live model.

## Execution gates still required

Finish the S01A/S02 schema/authority/budget/cancellation/known-result/effect fault
matrix, independent upgrade/drain/rollback cases, all Context provenance/redaction/ladder
requirements and independent AC-M17/AC-M48/NFR-M48 proofs. Then publish the Host
contract version and evaluate RP-00–RP-02. The S06 session scope (coordinator,
recovery and the interactive REPL front-end) carries named development proofs on
the real daemon; the full S04–S07 release matrices, the live Provider proof and
the S07 Evolution scope remain scheduled; no dependency is VERIFIED.

## Frozen Context development profile

ADR 039 provides generic Context mechanisms through the public `sdk.context` API.
Seed selects its own input schema, echo operation, explicit fake Provider profile,
16,384-byte budget and reject-on-overflow policy. These are content-addressed
resources referenced by AMPAK runtime constraints, without changing the frozen
Harness manifest fields. Host freezes authorized sources at Task acceptance and
independently recomputes all submitted sections/provenance/counts. The five-section
20/30/20/15/15 ladder carries unused quota forward and counts delimiters. The
fake Provider reads the redacted projected input; a daemon test compares a bearer
secret workload with the exact expected redacted terminal ArtifactId. State
contents and arbitrary live Fact queries are not exposed by this snapshot.

Runtime-owned tests cover full-schema overflow, Unicode truncation, normalization,
redaction before Fact selection, exact resource identities and 100 stable replays.
`tests/contract/test_context_projection.py` also installs a separately signed
consumer probe package in a real daemon. Six forged requests fail with
INVALID_RESULT before any Invocation, and 100 Context requests over one frozen
Task retain exactly the same projection identity/provenance/rendered bytes and
then complete through the actual fake Provider. This caught and fixed replay
invalidation of an earlier Host-issued projection object. Public causal queries
confirm zero calls for forgeries and exactly one model call for the replay case.
Determinism and provenance now extend beyond one frozen Task: distinct Tasks
share the exact provenance frame (policy/redaction-policy artifacts, per-section
renderers, normalized source set) with only the task_input body and the Task's
own input Artifact differing, every artifact-shaped provenance reference
resolves to its content-addressed bytes (fact/runtime references are
generation-scoped UUIDs bound to content hashes), and the same input projects
byte-identically in a fresh daemon generation, stored manifest included minus
per-projection identity/time fields.

The complete Context/AC-M48/NFR-M48 matrix remains required; these development
changes do not promote a dependency or advertise Host SPI 1.0.0.

## Loop and tool conformance preparation

The named `test_loop_semantics.py` and `test_tool_dispatch.py` modules install
independently signed Seed packages with a scripted consumer Provider and PURE
echo adapter. They execute through the same real Host as the default fake
Provider, without Runtime state mutation or test readiness. Cases cover complete
terminal parts, LENGTH, textual non-dispatch, invalid/empty responses, unknown
cost, policy/Task ceilings, serial 16-call dispatch, 17-call rejection, global
call IDs, complete assistant/tool history, schema failures and explicit
stop/continue-on-error behavior. Causal queries check actual invocation counts;
terminal ArtifactIds match independently encoded expected results. These are
development proofs; the remaining fault, deadline/authority, release and
platform matrix still applies.

## Public execution inspection and process-loss proofs

Public API 1.2 adds `client.get_task_execution(task_id)` and CLI
`agent-meta task execution <task-id>`. Its schema-version-one resource contains
bounded Invocation states/normalized usage/artifact references, projection
manifests and accepted/consumed budgets. It exposes neither storage paths nor
Provider-native objects or raw contents. It is an authenticated local operator
read, separate from the Harness facade. Older negotiated minors refuse it.

`test_host_recovery.py` kills a real owner with a model result either confirmed
or still RUNNING. `test_loop_recovery.py` does the same at a PURE tool boundary
after a model result. The consumer's own Provider/tool callbacks emit nonsecret
observation markers to the daemon's captured console; tests read that public
process output and public execution metadata, never Runtime DB/CAS/key paths.
Random model content, preserved Invocation/output/projection IDs and unchanged
consumed counts establish confirmed replay. UNKNOWN stops without another
callback. Confirmed tool history is reconstructed in order before the next
model call. These cases do not establish irreversible effects, hard isolation,
the entire cancellation/fault matrix or a release compatibility declaration.

`test_task_replay.py` covers the envelope-level slice of the RP-05 matrix. A
committed `Task.Submit` response is discarded at the consumer Transport return
boundary and the owned daemon is then killed between the confirmed model result
and the Task terminal. The restarted daemon replays the exact signed envelope
bytes to a wire receipt that is byte-identical to the discarded one — the same
Task identity and serving revision — reissues the identical durable receipt on
further replays, and completes the unique terminal from the already-confirmed
result with no second Provider callback across daemon generations. A dropped
`Task.Wait` response with the daemon alive is re-observed byte-identically
through a fresh connection. A plain restart also serves brand-new Tasks under
the same frozen serving revision and Composition — serving advances only through
a reviewed package cutover, not process loss. The same file closes two S02
injection leftovers: a cancel inside a consumer-side pre-dispatch window (the
loop idles before any projection) takes effect cooperatively with zero
invocations, projections or Provider callbacks, and after restart both the
submit and cancel envelopes replay their durable receipts without resurrecting
the Task; an UNKNOWN-outcome submit (daemon killed mid-callback) replays its
durable receipt with the FAILED_RECOVERY/EXTERNAL_EFFECT_UNKNOWN terminal and
never re-executes. These are development checkpoints;
RP-05 stays OPEN until release evidence closes it.

## Upgrade and uninstall ownership

`test_release_lifecycle.py` builds new package versions with explicit descriptor
revisions, verifies real cutover, drains a confirmed old Task with its frozen
Composition/Surface, and uninstalls the old installation while the new version
continues serving. An unhealthy next candidate leaves the healthy serving
version usable. A separate case checks that cutover's immediate scoped-grant
revocation denies the old Task's next tool call; it cannot use a new installation
grant or bootstrap Root authority. Confirmed work can drain without obtaining
another effect authorization. The rollback direction is now proven from the
consumer side as well: activating the old installation while a Task is
mid-flight under the NEW version drains that Task frozen under its v2
Composition/meta revision, advances serving to the rolled-back package, and
new Tasks execute the old version under a fresh Composition. Rolling back to
a use-limited old installation re-mints its frozen grant requests as a new
generation with the `max_uses` limit intact — the first Task succeeds under
the restored version, consuming the generation's single permitted use, and
the next Task is refused `AUTHORITY_DENIED` at its first tool call after
exactly one SUCCEEDED model invocation across the generation, with serving
kept on the rolled-back revision, and the denial triggers no fallback or
reactivation of either installation. The fault side of the lifecycle is
pinned too: an UNINSTALLED identity is terminal — a rollback activation and
even a plain reinstall of the same signed package are both refused
`FAILED_PRECONDITION` ("history never revives") — and the currently-serving
ACTIVE installation cannot be uninstalled out from under serving. A second,
distinct signed rollback envelope is not a replay: it re-approves the same
old package as a fresh grant generation with disjoint grant IDs and a new
Composition while confirmed work keeps its exact receipts; only the exact
envelope bytes replay idempotently. In-place replacement is impossible: a
fully valid signed bundle with the same name/version but a different
descriptor revision carries a different manifest hash and is refused
`IDEMPOTENCY_CONFLICT` ("publish a new version"), and of two activation
envelopes prepared from the same base revision exactly one wins — the
superseded envelope is refused `REVISION_CONFLICT` while the winner's
receipt replays unchanged. Grant admission bounds the whole chain: a grant
request that can never be exercised (zero uses) fails package validation
(`grant_requests.invalid`) before installation, before activation and
before any serving impact.

Runtime ADR 041 checks uninstall references by installation ownership, including
State owners and unsettled Effects. Unrelated serving work no longer blocks
removing a drained old package. The builder accepts explicit descriptor revision
and validated loop policy; the package CLI exposes `--descriptor-revision`.
The named consumer rollback cases above cover reverse-direction drain,
grant-generation limit inheritance, the uninstall/reactivation terminal
fault matrix, the descriptor-revision in-place-replacement prohibition,
superseded-activation conflicts and impossible-grant admission refusal;
wider crash/authority cases and release evidence remain required. The full
S04–S07 scope remains unverified.

## Independent Host contract matrix

The named `test_host_contract.py` module installs a separately signed consumer
adapter. Actual task-free health probes and immutable Task/View/Surface/Context
values are checked inside that adapter. Public execution inspection confirms
that unissued/cloned/foreign-Task projections, calls before a model, out-of-order
or altered/repeated tool calls, pending-tool model calls and forged/early terminal
results cannot create additional invocations or a terminal Artifact. Restricted
activation policies separately exhaust model and tool grants while the operator
still has Root authority; the Host refuses another call and does not debit a
denied invocation. This matrix remains development evidence until the remaining
epoch/fault and release gates are complete; the principal and deadline cases
described below add bounded development coverage.

## Ordinary content inspection

Public API 1.3 adds `client.get_artifact_content(artifact_id) -> bytes` and CLI
`artifact content <id>`. Only ordinary content up to 1 MiB is supported. The
service and SDK independently verify size/hash; encrypted or tombstoned
classifications are refused without trying a plaintext copy. This is operator
inspection, not a new execution facade or restricted-read permission.

`test_artifact_content.py` uses installed wheels, public upload/read/verify and
the real daemon to compare binary/empty/boundary bytes, explicit limits and
unchanged observation revisions. The Context test now reads the actual
ProjectionManifest, section outputs and concatenated rendering through this API
and checks exact hashes and token counts. Bootstrap compares actual terminal
bytes with independently encoded expected multipart results. No test reads
Runtime storage paths. RP-04 stays OPEN for controlled Host tools, State and
Scratch; these ordinary reads do not establish raw retention/decryption.

## Strict admission, timeout and cancellation

ADR 043 makes SDK/CLI/server share strict Task budget/deadline validation.
Budgets cannot silently cast booleans/fractions/strings or discard falsy input;
the CLI rejects malformed/duplicate JSON fields. `task submit --deadline-at-us`
exposes the existing absolute microsecond field. Zero remains an expired
deadline, and dry-run validates the same payload without staging snapshots.

The named Host matrix now checks literal expired deadlines with no model or
projection, timeout during an actual waiting model callback, cancellation of
in-flight and already-confirmed results, and unchanged consumed counters.
A separate later cancel command receives FAILED_PRECONDITION after terminal;
the result and invocation records remain unchanged. This is distinct from
replaying the same complete signed command, whose full matrix remains RP-05.
The cooperative profile still does not establish hard preemption/isolation.

## Ordinary actor keys and attenuated authority

ADR 044 adds Public API 1.4's `Authority.CreatePrincipal/Delegate/Revoke` and
matching SDK methods/CLI commands. A consumer generates and retains its own
Ed25519 key, registers only the public bytes through operator administration,
then connects with `CommandAuthority(actor_id, grant_id, key.sign)`. Ordinary
AGENT/CAPABILITY/PEER identities cannot create a second Root or Runtime Service.
Delegation uses the exact signed parent, strictly contains permissions/scope/
time/epoch/uses/depth, and consumes one command use. Amount ceilings are rejected
as unavailable until amount accounting is implemented.

`test_actor_authority.py` exercises the installed wheel and actual daemon with
these consumer-owned keys. Missing, wrong-scope, exhausted and expired model
authority cannot borrow the operator or Harness Service's permissions. The
frozen Surface excludes unauthorized tools; Seed's selected echo schema then
causes Context to refuse before model dispatch. A fully scoped actor completes
the model/tool/model chain. Separate scheduling windows revoke model/tool
authority after projection or a confirmed model result: the next call is denied,
with unchanged prior Invocation/projection IDs and consumed counts and no denied
callback. Public delegation with one remaining use succeeds once, replays the
same receipt and refuses another command. Process output and public metadata
provide observations; consumer tests never open Runtime DB/CAS/key paths.

These cases extend SH-HOST-01. They do not close RP-01/RP-05/RP-07, publish
Host SPI 1.0 support, establish Epoch succession or replace release evidence.

## Cooperative Host scheduling

A full consumer run exposed a Hello deadline while one Task issued 100
immediate Context requests. ADR 045 adds a scheduling point outside all store
transactions at each async Host call boundary, then rechecks cancellation and
authority. This lets ready management I/O and cancellation run between calls;
it does not preempt a callback that blocks without awaiting. Scheduler-port
regressions and the real Context/Host matrix verify this bounded correction.

## Public Task state traces and determinism

ADR 046 adds API 1.5's bounded, read-only `get_task_trace(task_id)` / CLI
`task trace`. One SQLite snapshot returns actual Action status, ordered Fact
metadata and Task-scoped causal edges. It never infers missing transitions or
returns raw Fact payloads. This supports external sequence comparisons; it is
not the complete general Fact/Evidence/Evaluation query contract.

The named `test_nfr_m48.py` drives 100 distinct real Tasks using the default
Seed Loop/fake Provider/echo, a consumer-owned signing key, one declared input
and budget, and no runtime.reflect grant. Exact frozen Context source/content
hashes, Surface, state bindings, rendered sections, actual normalized requests,
model/tool output hashes, statuses/reasons and causal edges are compared.
Generated identities/times/absolute observation revisions are normalized only
at explicit paths documented in `tests/nfr_runtime.py`; derivative projection
request hashes are verified before normalization. Fact access is explicitly
unavailable/empty in this fixture, rather than substituting live changing Facts
for the same snapshot. This is a development proof in the current trusted
profile; AC-M17's InMemory Backend and complete release gates remain separate.

`tests/acceptance/test_ac_m48.py` runs ten response/budget cases twice each on
the real Host: text, multipart content, LENGTH, one/two tools, duplicate call ID,
empty response, error finish, exhausted budget and tool/shell-shaped free text.
It independently encodes expected terminal bytes, compares normalized actual
Action/Invocation/Fact graphs and observes consumer model/tool callback markers.
Text cases produce exactly one model callback and no tool callback/invocation;
they do not provide an isolation or InMemory Backend support claim.

## InMemory enforcement preparation

Runtime ADR 047 validates the specified Root-signed public Service certificate
and Service-signed JCS token, strict scope/time/ceiling binding and a bounded
thread-safe replay cache. ADR 049 registers the actual certificate in fresh
bootstrap, retains it through the initialization Fact and provides a signer
that opens only the protected Service key. It does not grant effect authority;
Actor and installation-scoped Service checks are still independently required.

ADR 048 repairs the existing InMemory adapter's negotiated-session/handle
checks, immutable request semantics, actual result Artifact, mandatory hash
acknowledgement, retention capacity and UNKNOWN cancellation behavior. Instances
without an injected execution verifier are explicitly contract-test-only. These
Runtime proofs alone do not replace AC-M17.

ADR 050 attaches an explicitly selected `in_memory` Host through actual
negotiate/submit/handle/await. Select it with `start --execution-backend in_memory`
or `execution.host_backend = "in_memory"` in TOML; the CLI option overrides
configuration and the frozen profile hash records the selection. Trust/session
failure refuses the selected path without fallback. Native package callbacks
are normalized inside Backend activity. The existing Actor + installation
Service checks and budget reservations still precede it.

Invocation confirmation, its actual Artifact and a terminal-ack outbox intent
commit atomically. Ack delivery occurs outside Meta transactions and retries
the exact result hash. A lost ephemeral session is recorded as
`UNAVAILABLE_SESSION_LOST`; no successful ack or durable Backend restoration is
invented. Confirmed results remain authoritative in Meta Store, and incomplete
results after owner loss remain UNKNOWN. Public API 1.6's optional
`execution_binding` exposes public audit IDs, handle hash, terminal hash and ack
state, without opaque handles/session secrets/token bytes. Current
`get_view(include_backend=True)` exposes the selected profile hash and features.

The named `tests/acceptance/test_ac_m17.py` installs Seed's own package and uses
an own-key Actor for context → fake model → echo → execution Facts → public why
→ completion. It verifies actual binding and ack metadata through public APIs.
The model/tool process-kill recovery suites also select this Backend and
independently observe callback counts. This is Windows development evidence;
the profile remains trusted Python, cooperative, zero-cost/PURE with EMULATED
persistence and no process/network/credential/hard-quota isolation claim.

## Evolution admission boundary

The named `tests/contract/test_evolution_policy.py` pins the fail-closed
admission order of the pinned Runtime's public Evolution commands on a real
daemon, without importing Runtime store modules. `Evolution.Propose` with an
unknown target composition refuses `NOT_FOUND`; against the real serving
composition it admits a Proposal whose `why` provenance resolves, and a bare
Proposal never moves serving refs. `Evolution.RunExperiment` refuses in
declared order — unknown criteria ArtifactId (`NOT_FOUND`), malformed
`deterministic-evaluation/v1` criteria (`INVALID_ARGUMENT` with named issues),
then the unregistered World (`NOT_FOUND` with the echoed `world_id`) — and an
ArtifactId passed in the CandidateId position never gets past admission.
`Evolution.Promote` refuses any unregistered Candidate, including an ArtifactId
in the CandidateId position, with `NOT_FOUND`. Every refusal commits nothing:
serving refs and the public meta revision are identical after the whole matrix,
so no Proposal/Experiment/Candidate/World is auto-created and serving never
drifts. An Actor without `experiment.run`/`composition.promote` authority is
refused `AUTHORITY_DENIED` on all three commands with the meta revision
unchanged.

Two boundaries are observed and left to their owners. World (and therefore
Candidate) registration has no public interface on the pinned Runtime wheel
(RP-06 OPEN; `create_world` has no command caller), so admission refusals are
provable only up to the World gate — deeper Candidate/Composition checks stay
unreachable rather than unexercised. The raw `Evolution.Propose` records
`source_evidence_ids` as opaque strings without resolving them; resolution is
entirely Seed-side responsibility.

The first collector leg now exists:
`agent_meta_seed_harness/evolution/collector.py` reads task history through
public bounded traces (`Task.GetTrace`), aggregates per-task action status and
failure modes into a canonical `seed-evolution-evidence/v1` fixture Artifact,
and authors a Proposal whose `source_evidence_ids` are resolved fail-closed
before anything is committed — `fact://` references must appear in the
observed traces (a probe showed `Graph.Why` cannot distinguish a real from a
fabricated well-formed id, so observed history is the only reliable anchor),
`artifact://` references must resolve through the public manifest, and
unknown task ids, empty history or unknown schemes exit as
`InsufficientEvidence` with no fixture, no Proposal and unchanged
serving/meta state. The named partial SH-EVO-01 module
`tests/acceptance/test_evolution_pipeline.py` pins the real-history Proposal
path with resolvable provenance and the whole refusal matrix on a real
daemon. The remaining S07 pipeline (Candidate/World/Experiment/Evaluation
fixture drive and governance) is unreachable on the pinned wheel and stays a
named gap.

The named partial SH-GOV-01 module `tests/contract/test_evolution_governance.py`
pins the wheel's conditional-revision governance on a real daemon:
`Evolution.Propose` admits a proposal conditioned on the caller's observed
`expected_meta_revision`, and a stale observation is refused
`REVISION_CONFLICT` (`command expected meta revision differs`, with expected
and actual values in the details) committing nothing.
`Evolution.Rollback` requires the `composition.rollback` permission
(`AUTHORITY_DENIED` otherwise), refuses a fabricated parent composition with
`NOT_FOUND`, and refuses a stale serving observation (`serving revision
changed since observation`) — every refusal leaves the public meta revision
and serving refs unchanged. The fixed adjudicator and signed binding are
Runtime-internal on this wheel and remain unpinned.

The first S08 artifact-candidate governance leg exists too:
`agent_meta_seed_harness/evolution/artifact_candidate.py` builds
`REPLACE_ARTIFACT` candidates fail-closed — the live old value is read
through the public Artifact store and the candidate is bound to its SHA-256
(stale expected hashes are refused after the artifact moves on), kinds
outside the whitelist (`tool_descriptor`, `skill_doc`, `prompt_policy`) are
refused before anything is built, a candidate may not replace its own frozen
evaluator, and the approval preview is a deterministic canonical hash/path
diff. The named partial SH-GOV-03 module
`tests/contract/test_evolution_artifact_governance.py` pins these legs on a
real daemon; the experiment/promotion legs stay gated (RP-06 OPEN). The
bounded trigger policy (`evolution/tool_trigger.py`) aggregates failure
modes from real task history through public bounded traces — empty history
never triggers — and enforces one Proposal per window with a per-target-path
cooldown that a fresh window cannot bypass and a frozen ceiling that refuses
wider policies; `tests/contract/test_evolution_artifact_policy.py` pins
these bounds over a real failing task.

The first S09 code-candidate governance leg exists too:
`agent_meta_seed_harness/evolution/package_candidate.py` treats a code
candidate as a full new AMPAK package version with no fast lane. The
candidate source tree is physically isolated — built from explicit copied
bytes that never mutate the live sources — and identity-bound: the same
package version cannot carry different content without advancing the
descriptor revision. The per-day candidate budget is bounded by a frozen
ceiling the builder cannot raise, and an exhausted or failed stage is
terminal — nothing is retried, rescheduled or looped. The named partial
SH-GOV-04 module `tests/contract/test_evolution_code_governance.py` pins
these legs and proves on a real daemon that the release gates are not
waivable: the candidate bundle is built through the same signed S03 path
with provenance bound to the isolated candidate tree, validates clean, while
a content drift that was not re-signed and a fabricated signature artifact
are both refused with `manifest.signature_invalid` — no path reaches a
valid manifest without the publisher's signing key, which never enters the
candidate generator context.

The named partial SH-EVO-05 module `tests/acceptance/test_evolution_code_release.py`
runs the code-candidate release drill end to end on a real daemon: a code
defect observed in real task history (a failed task whose public bounded
trace feeds the bounded trigger policy) generates one candidate through the
explicit single-pass staging (`evolution/code_release.py` — budget-gated
generation, provenance bound to the isolated tree, activation inputs
returned as plain data with nothing signed); the day's exhausted budget is
terminal with no retry or scheduled rerun; the candidate bundle installs
into its own slot; an activation envelope without the package's exact signed
grant requests — or with fabricated ones — is refused `AUTHORITY_DENIED`
committing nothing; the operator-signed activation cuts serving over while
the frozen old task drains under its frozen composition on the old version;
an unhealthy third candidate never realizes (desired advances, realized and
serving stay); and rollback is a fresh approved operator activation of the
old package whose receipt replays identically after a real owner restart
while confirmed results keep their exact receipts. The evidence-driven
generation pipeline upstream of the candidate tree (Candidate/World/
Experiment registration) stays gated (RP-06 OPEN).
