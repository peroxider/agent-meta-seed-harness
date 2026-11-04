# Changelog

## 0.1.0.dev1 — unreleased

- Independent project and public-consumer architecture checks.
- Versioned Runtime contract inputs and evidence-based release gates.
- Public State management consumer and exact signed-command replay after owned daemon kill.
- Signed development tools package with Artifact/State adapters, deterministic JSON normalization (same content-addressed output ArtifactId for identical calls on a real daemon), scoped grants, per-channel Scratch truncation marking, transcript-State refusal and controlled synthetic Provider integration.
- Consumer-side session coordinator and REPL front-end over the public message protocol: idempotent journal replay, pending-round recovery on attach, round lineage diagnostics and admission-refused rounds committed with their FAILED terminals.
- Release-lifecycle fault matrix: stale-plan refusal, envelope replay after owner restart, drained old-version serving, use-limited rollback re-minting and disjoint grant generations.
- Fail-closed model admission: a Provider profile that cannot state a firm pre-call maximum cost is refused before any wire request under a Task cost ceiling. The named SH-PROV-03 live-job module now gates explicit enablement and hard count/cost/timeout limits with missing-credential refusals that never report success.
- Provider recovery boundaries on real daemon processes: pre-send failure settles `NOT_SENT` with zero liability and is never resent; deadline or explicit cancel during an in-flight request settles the effect `UNKNOWN` with full liability, and a late upstream response cannot reverse the outcome. Credential containment: after a real model+tool run the secret value and derived hash appear on no public surface, and the public doctor scan reports zero findings.
- Fail-closed Evolution admission on a real daemon: unknown propose targets, unknown or malformed criteria artifacts, unregistered Worlds and unregistered candidates (including an ArtifactId in the CandidateId position) are refused with no object auto-created — serving refs and the public meta revision are identical after the whole refusal matrix — while a Proposal against the real serving composition is admitted with resolvable provenance and never moves serving.
- Product integration remains subject to the Runtime dependency ledger.
