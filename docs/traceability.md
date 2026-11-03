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
| SH-SESS-01 | session | IN_PROGRESS | Schema preparation in `tests/contract/test_session_documents.py` and `tests/contract/test_session_document_state.py`; required `tests/contract/test_session_consistency.py` remains open |
| SH-SESS-02 | session | PLANNED | `tests/acceptance/test_session_recovery.py` |
| SH-EVO-01 | evolution | PLANNED | `tests/acceptance/test_evolution_pipeline.py` |
| SH-EVO-02 | evolution | PLANNED | `tests/contract/test_evolution_policy.py` |
| SH-GOV-01 | evolution | PLANNED | `tests/contract/test_evolution_governance.py` |
| SH-GOV-02 | evolution | PLANNED | `tests/acceptance/test_evolution_release.py` |
