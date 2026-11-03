# Development status — 2026-11-03

The full S00 → S01 → S01A → S02 → S03 → S04 → S05 → S06 → S07 → S08 → S09 plan remains
in scope. Development is in progress; no product profile is released and all
RP-00–RP-07 dependencies remain OPEN. Machine reports under `reports/bootstrap/`
are explicitly DEVELOPMENT_ONLY and do not promote release statuses.

The updated plan includes `evolution-artifact` (S08) and `evolution-code` (S09).
The machine ledger and release CLI/CI choices now include their five new named
requirements, all PLANNED. These profiles accumulate every preceding gate;
S07 reports cannot establish S08/S09. Their implementations and required
consumer modules are still missing, so both release gates must reject.
Plan files are part of the source digest, sdist validation and clean release
snapshot: changing acceptance scope invalidates earlier consumer evidence.

## Implemented development path

- Independent repository, source/distribution namespace, public-only import
  audit, Windows/CPython 3.12 hash-pinned wheelhouse and offline installed-wheel
  tests. Builds do not read a neighboring Runtime checkout. Explicit contract
  preparation archives document/protobuf hashes and the exact Runtime wheel.
- Signed AMPAK bundles contain an explicit execution-source allowlist, source
  provenance, dependency lock, validated Loop policy, Context profile and
  descriptor revisions. Validate/Install do not execute package adapters.
- Real Windows Named Pipe SDK/CLI and daemon lifecycle use current-user peer
  identity, DPAPI, protected credential ACLs and signed public commands. The
  consumer never reads Runtime private keys, storage or implementation modules.
- An explicitly trusted in-process Host binds task-free factory/health, real
  serving reconciliation, frozen Task/View/Surface/Context and actual fake
  Provider/PURE echo calls. Seed owns its bounded serial Loop and application
  policy; Runtime authorizes, reserves, journals and completes execution.
- Context uses versioned policy/schema/normalizer/renderer/tokenizer artifacts,
  the five-section budget ladder, redaction before selection and independent
  Host recomputation. Six forged projections are refused; 100 requests over one
  frozen Task retain identical identity, provenance and rendered content.
- Loop/tool tests cover complete normalized terminal arrays, LENGTH, free-text
  non-dispatch, ordered history, schemas, policy/Task limits, 16/17 tool calls,
  global call IDs and stop/continue-on-error behavior, where a continued
  declared tool error still cannot bypass the next tool's authority check under
  an exhausted grant. The default loop's Task
  fact trace registers exactly the content-addressed projection manifest and no
  raw provider response artifact, and every inspected MODEL invocation output is
  normalized multipart bytes; the frozen loop policy schema rejects a
  raw-retention field, while saving an explicit-policy Restricted Raw Artifact
  has no public Host facade under the pinned Runtime contract, like Epoch
  succession. Host tests cover frozen
  DTOs, task-free health, unissued calls/projections/terminals, expired deadlines,
  active-call timeout/cancellation and scoped activation-grant exhaustion.
- The signed tools package covers the S05 operation matrix: artifact.put
  replays the same content-addressed receipt for an identical payload and an
  oversized workload is refused at admission before any invocation;
  seed.transform refuses input-schema violations before dispatch and duplicate
  JSON fields as a declared INVALID_ARGUMENT; state writes stay CAS-guarded
  with per-operation refusal codes, bounded artifact reads and redaction as
  recorded below.
- A consumer-side session coordinator (`agent_meta_seed_harness/session_coordinator.py`)
  now drives the S06 message protocol over public State CAS and exact signed commands
  against a real daemon: identical retries recover the original operation, a
  different input or a second pending message is a conflict, journal
  registration retains exact signed bytes without moving the transcript CAS
  and replays idempotently, the model projection's task_input body carries
  only the current input, an external transcript CAS conflict stops the round
  without merge or redispatch, summary provenance commits against real
  committed history, and rounds share one frozen serving revision. The named
  SH-SESS-02 recovery proof (`test_session_recovery.py`) kills the daemon at
  each protocol boundary — pending before submit, ambiguous journal write,
  lost submit receipt, terminal before writeback, writeback response loss —
  and recovers from committed State only, replaying exact journaled bytes
  with one Task, one model call and one append per message; failed and
  cancelled terminals are recorded without redispatch and a Seed upgrade
  preserves both session States. The plan's minimal front-end and round
diagnostics (`agent_meta_seed_harness/repl.py`) propose stable message
identities, recover any pending round on attach before new admission and
explain a round's lineage from transcript, journal and public Task trace;
`tests/contract/test_session_repl.py` proves both against a real daemon.
- Public inspection returns bounded Task/Invocation/projection metadata and
  ordinary Artifact content with independent size/hash verification. It does
  not expose Restricted content or native objects. Literal zero deadlines and
  malformed budgets are handled without implicit widening. The public State
  matrix now covers every retained historical revision across a daemon
  restart (exact per-revision content, current CAS/pointer, unknown revision
  refusal, redacted cross-actor history reads) and the revocation boundary:
  an already-accepted command keeps replaying its durable receipt after grant
  revocation, while any new command under the revoked grant is denied.
- Actual daemon process-loss tests preserve confirmed model/tool results,
  counters and IDs, reconstruct history without redispatch and stop UNKNOWN
  outcomes. The envelope-level RP-05 slice (`tests/contract/test_task_replay.py`)
  drops a committed Task.Submit response at the consumer Transport boundary and
  kills the daemon before the Task terminal: the restarted daemon replays the
  exact signed bytes to a byte-identical wire receipt (same Task identity and
  serving revision), reissues the identical receipt on further replays, and
  completes the unique terminal without a second model call; a lost Task.Wait
  response is re-observed byte-identically, and a plain restart keeps new Tasks
  on the frozen serving revision/Composition (only a reviewed cutover advances
  serving). The same file injects a cancel inside a pre-dispatch window —
  cooperative cancellation lands with zero invocations/projections/Provider
  callbacks and both envelopes replay durable receipts after restart — and
  replays an UNKNOWN-outcome submit to its durable receipt without
  re-execution.
  Upgrade tests cover cutover, frozen confirmed-work drain, removal
  of a drained old package while the new version serves and a bad candidate
  preserving healthy serving. Cutover immediately revokes old scoped grants.
- Public API 1.4 adds ordinary own-key Actor registration, bounded delegation
  and authorized revocation. Consumer tests separate acceptance-time Surface
  filtering from invocation-time checks and revoke permissions at actual
  model/tool boundaries. Runtime rejects unenforced amount ceilings explicitly.
- Public API 1.5 adds bounded actual Task/Action/Fact state traces. The named
  NFR-M48 test executes 100 distinct own-key Tasks and compares exact frozen
  content/Context sources, actual requests, outputs, ordered states and causal
  edges under an explicit identity/time normalization policy. Named AC-M48
  covers ten repeated response/budget fixtures and independently counts real
  model/tool callbacks; text-shaped tool/JSON/shell instructions remain inert.
- Development wheel/sdist, CycloneDX SBOM and provenance bind exact input
  hashes. S03 now verifies actual wheel metadata/source bytes, sdist inputs,
  every locked binary, archived contracts, SBOM hashes, build provenance and
  signed AMPAK source/lock/Artifact closure. Dependencies must carry actual
  named consumer reports for the same inputs/commit/profile; a status and two
  plausible hashes cannot close them. Development and INSECURE_TEST_ONLY
  reports cannot become release evidence. Release preparation references the
  exact tested artifacts without rebuilding or publishing them.
- Runtime ADR 047–049 add strict Root→Service execution-token verification,
  actual public certificate bootstrap and a scoped Service-only signer. The
  existing InMemory adapter now checks negotiated sessions/handle identity,
  immutable replay semantics, actual Artifact outcomes, bounded retention and
  cooperative cancellation uncertainty.
- ADR 050 attaches actual InMemory Host activities through explicit selection,
  verified Service tokens and real handle bindings. Terminal confirmation and
  ack intent commit together; delivery retries outside transactions and records
  a lost ephemeral session explicitly. Public API 1.6 exposes bounded binding
  hashes/audit IDs and current profile metadata. Named AC-M17 and actual
  model/tool process-kill suites exercise the selected path in development.
- Stateless package rollback now uses a newly approved activation of the old
  installed package with a fresh Composition and grant generation. Both Host
  profiles reject a stale plan, replay the exact committed activation response
  after response loss and a real owner restart, preserve historical confirmed
  work, and refuse reactivation of an uninstalled package. This is not generic
  Evolution rollback or managed State restoration.
- The Windows CI consumer now accepts an explicit signed public package bundle,
  builds distributions/SBOM/provenance before tests, and invokes the owned
  prebuilt consumer producer. The release job consumes its exact evidence
  artifact without rebuilding. Hosted CI, assertion review, approved publisher
  configuration and product support remain unverified.
- Runtime Evolution graph lookup now constrains Composition, Candidate,
  Experiment and World references to the command Realm, including retained
  malformed graphs. Equal revision numbers in different Realms cannot redirect
  a rollback to a local Composition. Internal regressions do not close S07's
  public registration/governance requirements. Generic RESTORE_PARENT still
  lacks complete current-State CAS and historical serving bindings and remains
  an open implementation defect, separate from approved package reactivation.
- The first selected S04 direction is the operator's existing Volcano gateway
  using the Anthropic-compatible protocol and `glm-5.3-flash`. A bounded
  terminal-only codec now covers exact model binding, text/typed tool order,
  truncation, unknown usage/cost, malformed/partial response refusal and
  sanitized errors. Synthetic replay tests verify normalized byte identity;
  they are not captured R2 traffic. No credential is copied into this project,
  minimal's execution entrypoint is unchanged. A later native operator diagnostic
  sent one authorized quota-only request and observed HTTP 200, reasoning/text
  and final `OK`. That diagnostic is not a product live Task or captured R2;
  exact tokenizer, continuation and full usage accounting remain open.

Details and named consumer proofs are in [Host integration](host-integration.md).
The exact current versions/hashes are in `ci-inputs.json` and
`runtime-contract/manifest.json`; the advertised packaging contract stays 1.1.0.
Host SPI 1.0.0/Harness Contract 1.2.0 have not been declared supported.

## Remaining work and verification limits

1. Complete S01A/S02's full fault, Epoch, historical-query and stable command
   replay/denial matrix; finish independent Context determinism and provenance
   requirements beyond one frozen Task's repeated projections.
2. Complete final release report production, reviewed publisher configuration
   and the remaining execution-profile/platform matrix;
   the NFR-M48/AC-M48 Windows development cases still require the final
   CI/release manifest evidence before verification. Finish
   rollback and remaining lifecycle faults; evaluate the complete S03 manifest.
3. Implement S04 controlled Provider credentials/egress/cost and live-provider
   proof, S05 controlled Artifact/State/isolated Scratch, S06 session consistency
   and recovery, and S07 public Evolution registration/governance/release.

The current Host is cooperative trusted Python, zero-cost fake Provider and
PURE tools with `utf8-bytes/v1` Context accounting. It does not prove isolation,
hard preemption, paid-provider token/cost enforcement or irreversible effects.
No external release gate is closed by a Runtime unit test or file existence.

The optional Messages Provider package now supplies public plan/normalization
callbacks, signed model/profile declarations and a separate executable source
allowlist. Its public-only consumer tests start the explicit native loopback/TEST
Runtime launcher, provision synthetic credentials through the separate native
console, approve via signed public commands and use a consumer-owned Actor for
Tasks. They cover text/tool history, independent wire billing, unknown usage,
accepted disconnect and pre-admission refusal. Minimal still uses its original
fake binding. These synthetic checks do not establish the selected GLM gateway,
captured R2, a real exact tokenizer/tariff, Managed/EffectIntent or RP-03 closure.

The current Runtime development pin passed all 1560 unit cases on its frozen
input revision, without module exclusions. The Windows worker defects were
repaired in ADR 072; native recovery is covered by ADR 075. The same pinned
wheel passed 267 installed Runtime checks and 39 public Seed recovery checks
per Windows/Linux profile. Its fresh full installed Windows Seed regression
passed 393 cases with byte-verified, non-editable wheels. These results do not
certify strong isolation or release readiness. Non-Windows fixture credentials
remain INSECURE_TEST_ONLY. See `docs/runtime-dependencies.md` for exact evidence.

Completed checkpoints are recorded in `reports/platform-matrix.json` and their
named `reports/owned-*/environment.json` documents, with immutable Windows/Linux
exports preserving each generation's source, locked wheels, signatures and
report hashes. Focused in-progress checks are separate from a completed full
consumer run. The minimal gate remains unsatisfied; see each run's gate output
and the traceability ledger. No checkpoint declares product support.
