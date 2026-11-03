# ADR 038 — Harness source audit, serving health and restart ownership

Status: development implementation, independent consumer expansion in progress.
Date: 2026-10-30. Extends ADR 031/036/037; no requirement status is promoted.

## Source boundary during package validation

ValidatePackage audits every Python source in the AMPAK, including modules not
reachable from the entrypoint. It still never imports, extracts or executes
package code. Supported Runtime imports are explicit public `sdk` or
`protocols.public` paths; private imports, private module-member access,
Runtime vendoring and opaque/star Runtime imports are rejected. Literal dynamic
imports use the same boundary; nonliteral targets, dynamic relative imports,
opaque loaders and mutation of Python import search paths are unsupported.
Simple importer/path aliases retain their possible bindings for the audit.

Descriptors and template slots must reference this package's exact AMPAK code
artifact, and a Harness package must declare its `harness` artifact kind.
Provenance `source_files` must equal the complete decoded payload path/hash
map; a supplied lock reference must match package metadata. Scoped grants must
match the template Realm and declared Capability identities. These checks run
at Validate/Install, before any activation or factory execution.

Validation is bounded to 16 MiB aggregate Python source, 1 MiB per module,
200,000 AST nodes and bounded alias sets. Invalid/oversized unused Python files
fail validation too. Stable issues identify a reason, canonical package path
and line, without copying source text into diagnostics. Existing manifest,
AMPAK and RPC field layouts are unchanged; this tightens development validation.

This is a source/API-boundary audit, not arbitrary Python security. Explicitly
trusted in-process Python remains capable of reflection and native effects.
Strong isolation, credential/egress policy and unsupported execution placements
must be enforced by their Backend; an audit cannot establish those properties.

## Serving remains independent of a failing desired candidate

Readiness now accepts an actual serving-health port. The daemon supplies the
live installed-package catalog, rather than interpreting the desired cycle's
READY/FAILED value as the health of the current serving revision. Core and
backpressure gates still apply; UNKNOWN remains a core failure. A healthy old
serving composition continues accepting Tasks during a failed candidate
transition (§41.10/41.51, AC-M24). Failure revokes only candidate grants.

After owner restart, the application separately restores the actual serving
snapshot and compositions pinned by nonterminal Tasks. Each reruns package
verification, publisher trust, the real factory and PURE health using its
original stable reconcile/request IDs. This path does not change desired refs
or retry a FAILED candidate. Failed rebinds remove health, mark actual instances
unavailable and terminate unsafe frozen Task recovery explicitly. A removed
publisher trust entry cannot retain execution through stale READY rows.
Current GetView readiness uses the same evaluator as GetInfo, so a failed
candidate does not produce contradictory current readiness booleans. Historical
views retain their historical read path and never query current native health.

## Correct architecture enforcement and Service authorization

The AST lint previously resolved a source relative import as
`src.agent_meta_runtime...`, bypassing declared layer bans. It now resolves
against the actual Python import root, retaining the same forbidden rules.
Reconciler persistence is explicitly injected through `ports.reconciliation`;
its SQLite adapter owns the existing store mutators. Readiness consumes the
logical Meta schema version from a pure contract module. The daemon injects
its actual Service command runner for every reconcile mutation, checking the
active grant/current epoch and reserving a control use in the same transaction.
The application no longer imports the concrete store adapter.

The current owner explicitly reports its assembled trusted in-process profile,
not the nominal Portable worker feature map. It does not have process/activity/
workspace/isolation Backend operations attached. Such required features fail
package validation; the frozen Task View and Surface cache key use a SHA-256
of the actual profile declaration. Experiment validation consumes that same
feature map. Serving readiness and every control transaction also recheck the
active Service principal and its current control grant.
If an accepted Task's frozen profile is unavailable after restart, recovery
fails explicitly instead of replaying its Loop under a different profile.

## Evidence and outstanding work

Runtime package tests exercise private/dynamic/aliased imports, path mutation,
unused invalid modules, source limits and non-execution. Architecture regressions
inject forbidden relative imports under domain/application/ports/sdk and test
an allowed port import. Real AMPAK tests verify failed upgrade preservation,
actual old-serving Task execution before/after restart, scoped-grant isolation,
logical instance rebinding and loss of publisher trust during frozen recovery.

Seed adds public installed-wheel validation negatives and an entrypoint marker
test for Validate/Install non-execution. It also tests equivalent installs,
signed-policy name/version conflicts and non-resurrection after uninstall.
The complete S01A/S02 fault matrix, full Context requirements, isolated Backend
profiles and S04–S07 remain required. These bounded proofs do not certify the
whole Seed or Runtime release.
