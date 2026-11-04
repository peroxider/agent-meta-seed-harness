# Changelog

## 0.1.0.dev1 — unreleased

- Independent project and public-consumer architecture checks.
- Versioned Runtime contract inputs and evidence-based release gates.
- Public State management consumer and exact signed-command replay after owned daemon kill.
- Signed development tools package with Artifact/State adapters, deterministic JSON normalization, scoped grants, per-channel Scratch truncation marking, transcript-State refusal and controlled synthetic Provider integration.
- Consumer-side session coordinator and REPL front-end over the public message protocol: idempotent journal replay, pending-round recovery on attach, round lineage diagnostics and admission-refused rounds committed with their FAILED terminals.
- Release-lifecycle fault matrix: stale-plan refusal, envelope replay after owner restart, drained old-version serving, use-limited rollback re-minting and disjoint grant generations.
- Fail-closed model admission: a Provider profile that cannot state a firm pre-call maximum cost is refused before any wire request under a Task cost ceiling.
- Provider recovery boundaries on real daemon processes: pre-send failure settles `NOT_SENT` with zero liability and is never resent; deadline during an in-flight request settles `UNKNOWN` with full liability, and a late upstream response cannot reverse the outcome.
- Product integration remains subject to the Runtime dependency ledger.
