# ADR 039: Frozen Context policies and independent Host recomputation

Date: 2026-10-30
Status: development implementation; RP-01/RP-02 and external Seed gates remain OPEN

## Decision

Publish generic, deterministic Context mechanisms in `agent_meta_runtime.sdk.context`.
The external Harness selects its application input schema, operations, Provider
profile, budget and overflow policy. Runtime imports no Seed policy or code.
This extends the development Host from ADR 037; it does not advertise Harness
Contract 1.2.0 / Host SPI 1.0.0 before the complete independent matrix passes.

An AMPAK may reference `context_profile_artifact_id` in the existing
`PackageMeta.runtime_constraints`. The frozen Harness manifest field set is
unchanged. The profile addresses policy, minimum redaction policy, tokenizer,
Provider profile and five renderer declarations; policy addresses input, runtime
summary and Fact normalizer schemas. Package validation verifies the transitive
artifact hashes and installation retains them. Missing Context support cannot
establish serving health for this execution profile.

Task admission freezes the profile identity, Epoch Constitution, runtime summary
and authorized Fact candidates in the acceptance View. Snapshot roots are the
serving Composition, bound State/revision references and an optional authorized
causal parent Action. Fact selection follows undirected causal edges through
depth four, within the realm and a frozen sequence boundary. Realm-wide
`runtime.reflect` authority is required for Fact contents; without it the snapshot
contains no Facts. A policy requiring Facts fails explicitly. Source ceilings
reject admission rather than silently preselecting candidates before redaction.
The transaction recomputes the complete snapshot before acceptance. Subsequent
execution and recovery read these immutable sources, not current mutable views.

`TaskEnvelope.context` contains only immutable bytes, IDs and availability data.
The runtime summary currently contains State revision bindings, not State values;
this is not the RP-04 State read/write interface. Initialization registers actual
CAS paths for built-in artifacts so Constitution reads verify stored bytes.

## Projection rules

The versioned `jcs-ladder/v1` mechanism normalizes schema-known fields, redacts
minimum sensitive keys and fixed credential patterns, and then ranks and budgets
content. Facts sort by causal distance ascending, sequence descending, identity
ascending. Source hashes still identify original frozen revisions even when
redaction makes their rendered bytes equal. Selected operations include their
actual complete input/output schemas from the frozen Capability Surface.

Integer quotas are 20/30/20/15/15 percent in fixed system/input/schema/summary/Fact
order, with rounding remainder in the last segment. Unused quota rolls into the
next segment. Delimiters consume quota. System and selected schemas must fit in
full; input rejects overflow unless the policy explicitly permits a Unicode
prefix of one named string field. Runtime summary and ordered Fact prefixes are
bounded deterministically. An allocation never invents unused Fact demand.

The initial exact tokenizer is `utf8-bytes/v1`, with an explicit tokenizer
Artifact and matching Provider profile. It counts UTF-8 bytes, including section
delimiters; it does not estimate tokens for a live model. Missing or mismatched
tokenizers/renderers fail before a Provider invocation. Other exact tokenizer
profiles require an explicit supported implementation.

The package submits `ProjectionInput`. Host independently rebuilds the expected
request over the frozen snapshot and compares every field before staging any
projection artifact. Forged content, counts, source references, policy, renderer
or budget are rejected. Only Host-issued projections can reach model invocation.
Projection records preserve all policy/resource/source provenance, register
content-addressed sections and rendered bytes, and append one registration Fact.
Known projection replay preserves the projection ID without another registration
Fact. Service projection mutations authorize `runtime.project`; Task lifecycle
mutations authorize `task.execute`.

Seed's fake Provider consumes the projected task-input section. Raw input in the
Task DTO must not bypass its Context policy. The trusted in-process placement
remains cooperative and is not Python isolation or an egress security boundary.

## Evidence and limits

`tests/unit/test_context_contract.py` covers exact accounting, required sections,
redaction before selection, schema normalization, source provenance, Unicode
truncation, missing resources/tokenizers, authorization policy and 100 identical
replays. `test_bound_harness.py` uses actual signed AMPAK execution/recovery and
rejects six independent projection forgeries before any invocation. Bootstrap
tests open and hash-verify the stored built-ins. These Runtime-owned proofs do
not close the external Seed AC-M17/AC-M48/NFR-M48 or release gates. Independent
wheel/daemon tests additionally check redacted input reaches the fake Provider;
the full Context/fault matrix and public inspection proofs remain required.
