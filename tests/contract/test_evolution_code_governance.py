"""SH-GOV-04 (partial): code-candidate governance legs over public surfaces.

A code candidate is a full new AMPAK package version that walks the same
S03 gates as any human release. These legs pin the consumer-side bounds:
the candidate tree is physically isolated from the live sources and never
mutates them, the same identity cannot carry different content without a
descriptor-revision advance, the per-day candidate budget is bounded by a
frozen ceiling the candidate builder cannot raise, an exhausted stage is
terminal (failures are never retried or scheduled — no resident loop
exists), and the release gates are not waivable: a drifted or fabricated
signature is refused on a real daemon, so no path reaches a valid manifest
without the publisher's signing key, which never enters the candidate
generator context.
"""
import asyncio
import json
from importlib.resources import files
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.evolution.package_candidate import (
    CODE_BUDGET_CEILING, CandidateBudget, CodeCandidateError, build_candidate_tree)
from agent_meta_seed_harness.packaging import EXECUTION_SOURCE_PATHS, require_bundle_inputs
from seed_package import seed_bundle
from seed_runtime import admin, running_daemon


def live_sources():
    return {name: files('agent_meta_seed_harness').joinpath(name.split('/', 1)[1]).read_bytes()
        for name in EXECUTION_SOURCE_PATHS}


def identity(tree):
    return sha256_hex(canonical_json({'sources': {path: sha256_hex(raw) for path, raw in sorted(tree.items())}}))


def test_candidate_tree_is_isolated_and_identity_bound():
    base = live_sources()
    target = 'agent_meta_seed_harness/loop.py'
    snapshot = dict(base)

    tree = build_candidate_tree(base, {target: base[target] + b'\n# candidate fix\n'},
        version='0.1.0-dev.2', descriptor_revision=2, previous=None)
    assert base == snapshot, 'candidate construction mutated the live sources'
    assert tree == {**snapshot, target: snapshot[target] + b'\n# candidate fix\n'}

    previous = {'version': '0.1.0-dev.2', 'content_sha256': identity(tree), 'descriptor_revision': 2}
    different = base[target] + b'\n# different fix\n'
    with pytest.raises(CodeCandidateError, match='descriptor revision'):
        build_candidate_tree(base, {target: different}, version='0.1.0-dev.2',
            descriptor_revision=2, previous=previous)
    advanced = build_candidate_tree(base, {target: different}, version='0.1.0-dev.2',
        descriptor_revision=3, previous=previous)
    assert advanced[target] == different
    assert base == snapshot, 'refusal or advance path mutated the live sources'
    # Identical content under the same identity is not a new candidate.
    again = build_candidate_tree(base, {target: base[target] + b'\n# candidate fix\n'},
        version='0.1.0-dev.2', descriptor_revision=2, previous=previous)
    assert again == tree


def test_candidate_budget_is_bounded_by_the_frozen_ceiling_and_terminal():
    for key, ceiling in CODE_BUDGET_CEILING.items():
        wider = dict(CODE_BUDGET_CEILING)
        wider[key] = ceiling + 1
        with pytest.raises(CodeCandidateError, match=f'budget exceeds frozen ceiling: {key}'):
            CandidateBudget(**wider)

    budget = CandidateBudget(**CODE_BUDGET_CEILING)
    assert budget.register_candidate(day='2026-11-04', generation_tokens=1) == 0
    for _ in range(2):
        # Exhaustion is terminal: the failed day is never silently reopened
        # or rescheduled — the next candidate needs the next explicit day.
        with pytest.raises(CodeCandidateError, match='candidate budget exhausted'):
            budget.register_candidate(day='2026-11-04', generation_tokens=1)
    assert budget.register_candidate(day='2026-11-05', generation_tokens=1) == 0


def test_candidate_release_gates_are_not_waivable(tmp_path):
    base = live_sources()
    target = 'agent_meta_seed_harness/loop.py'
    tree = build_candidate_tree(base, {target: base[target] + b'\n# candidate fix\n'},
        version='0.1.0-dev.2', descriptor_revision=2, previous=None)
    candidate, publisher = seed_bundle(version='0.1.0-dev.2', descriptor_revision=2,
        overrides={path: raw for path, raw in tree.items() if base[path] != raw})
    root = Path(__file__).resolve().parents[2]
    require_bundle_inputs(candidate, files=tree,
        dependency_lock=(root / 'requirements-ci.lock').read_bytes(),
        contract_bundle_sha256=sha256_hex((root / 'docs/runtime-contract/manifest.json').read_bytes()))
    assert base == live_sources(), 'building the candidate bundle mutated the live sources'

    manifest = json.loads(candidate.artifacts[candidate.manifest_artifact_id])
    drifted = dict(manifest)
    drifted['package_version'] = '0.1.0-dev.3'
    fabricated = dict(manifest)
    fabricated['signature_artifact_id'] = 'artifact://sha256/' + sha256_hex(b'x' * 64)

    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        seen = set()

        def put(reference, raw):
            if reference in seen:
                return
            path = tmp_path / 'candidate-artifacts' / reference.rsplit('/', 1)[1]
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
            assert admin(data_dir, 'artifact', 'put', str(path), '--kind', 'code')['artifact_id'] == reference
            seen.add(reference)

        async def query():
            client = await connect(data_dir)
            try:
                for reference, raw in candidate.artifacts.items():
                    put(reference, raw)
                put(fabricated['signature_artifact_id'], b'x' * 64)
                healthy = await client.validate_harness_package(candidate.manifest_artifact_id)
                assert healthy['valid'], healthy
                for suspect in (drifted, fabricated):
                    reference = 'artifact://sha256/' + sha256_hex(canonical_json(suspect))
                    put(reference, canonical_json(suspect))
                    report = await client.validate_harness_package(reference)
                    assert not report['valid'], report
                    assert any(issue.startswith('manifest.signature_invalid') for issue in report['issues']), report
            finally:
                await client.aclose()
        asyncio.run(query())
    assert base == live_sources(), 'the release drill mutated the live sources'
