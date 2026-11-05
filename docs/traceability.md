# Seed traceability

Development status, not a release verdict. The machine-readable source is `traceability.json`.
Named AC-M17 now exercises explicitly selected actual InMemory activity,
Service authorization audit, real binding/terminal/ack, causal Facts and public
why through Seed's own package. The independent process-kill suites also cover
confirmed/UNKNOWN model and tool outcomes under this profile. Its status stays
IN_PROGRESS until complete CI/release evidence is bound; no RP dependency is
closed by this development result.
Only actual public-wheel Host proofs may promote a row to VERIFIED. Offline package
unit tests do not close Host, recovery or release gates.

Named SH-REL-02 now independently builds relocated offline wheel/sdist, verifies
the installed wheel bytes, source/lock/SBOM/provenance and signed AMPAK, and
rejects self-hashed stale or inconsistent artifacts. The report verifier binds
requirement and dependency JUnit/source/fixture/lock/contract/artifact inputs and
requires a reviewed publisher policy. It keeps DEVELOPMENT_ONLY evidence
distinct from release evidence. Full release/platform reports are still pending.

The named Context module now contains real public-wheel daemon proofs for six
forged projections and 100 frozen-context replays followed by a real fake-model
invocation. The whole SH-CTX-01 matrix is still IN_PROGRESS; this one module's
successful collection does not close other required proofs or dependencies.
The named Host contract module also exercises real frozen DTO/probe behavior,
unissued calls/terminals and scoped model/tool grant exhaustion. Host dependency
and release verification still require the complete remaining matrix.
Supplemental `tests/contract/test_actor_authority.py` adds own-key principal,
attenuation and immediate model/tool revocation cases without changing the
plan's fixed required proof paths or promoting their statuses.
The named NFR-M48 module now compares 100 real own-key Tasks under the declared
semantic normalization, and AC-M48 compares ten repeated fixtures including
inert textual instructions. Their status remains IN_PROGRESS pending final
profile/CI/release evidence. AC-M17 now exercises the selected actual InMemory
Backend in Windows development; the complete release matrix remains open.

| ID | Profile | Status | Required proofs |
|---|---|---|---|
| SH-BOOT-01 | minimal | IN_PROGRESS | `tests/contract/test_project_boundary.py` |
| SH-PKG-01 | minimal | IN_PROGRESS | `tests/contract/test_package_contract.py` |
| SH-HOST-01 | minimal | IN_PROGRESS | `tests/contract/test_public_imports.py`, `tests/contract/test_host_contract.py` |
| SH-HOST-02 | minimal | IN_PROGRESS | `tests/acceptance/test_host_bootstrap.py` |
| SH-LOOP-01 | minimal | IN_PROGRESS | `tests/contract/test_loop_semantics.py` |
| SH-CTX-01 | minimal | IN_PROGRESS | `tests/contract/test_context_projection.py` |
| SH-TOOL-01 | minimal | IN_PROGRESS | `tests/contract/test_tool_dispatch.py` |
| SH-REC-01 | minimal | IN_PROGRESS | `tests/contract/test_host_recovery.py`, `tests/contract/test_loop_recovery.py` |
| SH-REL-01 | minimal | IN_PROGRESS | `tests/acceptance/test_release_lifecycle.py` |
| SH-REL-02 | minimal | IN_PROGRESS | `tests/contract/test_release_evidence.py` |
| NFR-M48 | minimal | IN_PROGRESS | `tests/contract/test_nfr_m48.py` |
| AC-M17 | minimal | IN_PROGRESS | `tests/acceptance/test_ac_m17.py` |
| AC-M48 | minimal | IN_PROGRESS | `tests/acceptance/test_ac_m48.py` |
| SH-PROV-01 | provider | IN_PROGRESS | `tests/contract/test_provider_contract.py`, `test_provider_package.py`, `test_provider_host_binding.py` |
| SH-PROV-02 | provider | IN_PROGRESS | `tests/contract/test_provider_security.py`, `tests/contract/test_provider_replay.py`, `tests/contract/test_provider_recovery.py` |
| SH-PROV-03 | provider | PLANNED | `tests/acceptance/test_live_provider.py` |
| SH-CAP-01 | tools | IN_PROGRESS | `tests/contract/test_capability_toolset.py` |
| SH-CAP-02 | tools | IN_PROGRESS | `tests/acceptance/test_capability_toolset.py`, `tests/acceptance/test_scratch_tools.py`, `tests/acceptance/test_scratch_recovery.py`, `tests/acceptance/test_scratch_retirement.py`, `tests/acceptance/test_scratch_backup.py` |
| SH-SESS-01 | session | IN_PROGRESS | Schema preparation in `tests/contract/test_session_documents.py` and `tests/contract/test_session_document_state.py`; `tests/contract/test_session_consistency.py` now covers the named consistency matrix (dedup/conflict, concurrency refusal, summary provenance, journal non-self-expiry, control fields out of Projection, State conflict with frozen serving) in development |
| SH-SESS-02 | session | IN_PROGRESS | `tests/acceptance/test_session_recovery.py` kills the daemon at every named protocol boundary and recovers from committed State only; UNKNOWN (`FAILED_RECOVERY`) outcomes are recorded without redispatch and the session stays usable |
| SH-EVO-01 | evolution | IN_PROGRESS | `tests/acceptance/test_evolution_pipeline.py` drives failure history → collector fixtures → why-traceable Proposal/ChangeSet/Candidate against the public evolution surface; candidate/world registration stays Runtime-internal (RP-06), so the module also pins explicit NOT_FOUND refusals for unregistered references instead of fabricating registration |
| SH-EVO-02 | evolution | IN_PROGRESS | `tests/contract/test_evolution_policy.py` pins bounded trigger windows/attempt budgets, no-promotion exits, clone isolation and refusal scenarios in development |
| SH-GOV-01 | evolution | IN_PROGRESS | `tests/contract/test_evolution_governance.py` pins the frozen judge binding, signed composition authority and the permission/cross-package/stale-revision refusal matrix |
| SH-GOV-02 | evolution | IN_PROGRESS | `tests/acceptance/test_evolution_release.py` pins operator-approved activation, drain of the frozen old version and traceable rollback; a fresh-observation rollback is admitted and committed immediately |
| SH-EVO-03 | evolution-artifact | IN_PROGRESS | `tests/acceptance/test_evolution_tool_pipeline.py` drives the reachable artifact-candidate pipeline (failure-history trigger → whitelisted REPLACE_ARTIFACT/ADD_SLOT candidate with bound-in values and frozen criteria → deterministic preview) and honestly stops at the world gate with explicit refusals; promotion evidence is pending the Runtime-internal registration surface (RP-06) |
| SH-EVO-04 | evolution-artifact | IN_PROGRESS | `tests/contract/test_evolution_artifact_policy.py` pins the bounded trigger policy (window/cooldown/count), artifact-kind whitelist and the INVALID path; the `cooldown_us` lower-bound and trace-shape tolerance observations are recorded, not repaired |
| SH-GOV-03 | evolution-artifact | IN_PROGRESS | `tests/contract/test_evolution_artifact_governance.py` pins agent non-signing, artifact diff preview, old-value hash binding and evaluator independence |
| SH-EVO-05 | evolution-code | IN_PROGRESS | `tests/acceptance/test_evolution_code_release.py` rehearses code candidate → new AMPAK version → S03 gates → signed activation → drain/rollback, including idempotent receipt replay of a frozen envelope after restart |
| SH-GOV-04 | evolution-code | IN_PROGRESS | `tests/contract/test_evolution_code_governance.py` pins the non-exemptible gate, physical candidate-tree isolation, the daily budget under the frozen `CODE_BUDGET_CEILING` and the absence of a resident loop |

Supplemental `tests/contract/test_session_repl.py` exercises the plan's step 4/5
REPL front-end against a real daemon without changing the frozen proof paths:
pending rounds recover on attach before new admission, a dispatched-but-uncommitted
round explains its reserved submit identity and journal entry, the lineage query
moves the same message identity from pending to committed records, and an
admission-refused round is durably committed with its FAILED terminal, zero
invocations and a usable session afterwards.

The named S07–S09 evolution modules now pass as development proofs against the
public wheel: bounded policies, governance refusal matrices, the artifact
pipeline up to its reachable world gate, the conditional-revision/rollback
governance matrix and the full code-release rehearsal. Their rows stay
IN_PROGRESS: VERIFIED requires hash-bound consumer evidence from an approved
publisher CI run, and the RP-06/RP-07 dependency rows remain open.
