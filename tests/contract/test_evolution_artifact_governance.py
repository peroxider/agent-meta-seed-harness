"""SH-GOV-03 (partial): artifact-candidate governance over the public surface.

The pinned-wheel-provable legs: the candidate builder reads the live old
value through the public Artifact store and binds the candidate to its hash,
refuses kinds outside the S08 whitelist, refuses a stale expected old-value
hash after the live artifact changed, refuses a candidate that targets its
own frozen evaluator, and produces a deterministic canonical diff preview.
The experiment/promotion legs stay gated (RP-06 OPEN); agent-cannot-sign-
Promote is pinned by the Evolution authority refusals in
tests/contract/test_evolution_governance.py.
"""
import asyncio
import uuid

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.evolution.artifact_candidate import (
    ArtifactCandidateError, build_candidate, load_old_value, preview_diff)
from toolset_runtime import REALM, tools_environment


def unique(reference_type):
    return f'{reference_type}://019a44d0-0000-7000-8000-{uuid.uuid4().hex[:12]}'


def refused_build(**kwargs):
    with pytest.raises(ArtifactCandidateError) as caught:
        build_candidate(**kwargs)
    return caught.value


async def upload(client, actor, value, kind):
    return (await client.put_artifact(realm_id=REALM, actor_id=actor.actor_id,
        content=canonical_json(value), kind=kind, media_type='application/json'))['artifact_id']


async def refused(coroutine, message):
    with pytest.raises(ArtifactCandidateError) as caught:
        await coroutine
    assert message in str(caught.value), caught.value


def test_candidate_builder_binds_old_value_hash_and_whitelists_kinds(tmp_path):
    with tools_environment(tmp_path, actor_permissions=['artifact.put', 'capability.invoke', 'state.read', 'state.write']) as (owner, actor, state, replacement):
        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                old_descriptor = await upload(client, actor,
                    {'tool': 'seed.echo', 'input_schema': {'type': 'object'}}, 'tool_descriptor')
                content, observed = await load_old_value(client, actor, realm_id=REALM, target_artifact_id=old_descriptor)
                assert observed == sha256_hex(content)
                criteria = await upload(client, actor, {'deterministic': ['schema']}, 'criteria')
                criteria_sha256 = sha256_hex(canonical_json({'deterministic': ['schema']}))
                candidate = build_candidate(kind='tool_descriptor', target_artifact_id=old_descriptor,
                    expected_old_value_sha256=observed, observed_old_value_sha256=observed,
                    new_value={'tool': 'seed.echo', 'input_schema': {'type': 'object', 'additionalProperties': False}},
                    criteria_artifact_id=criteria, criteria_sha256=criteria_sha256)
                preview = preview_diff(content, candidate)
                assert preview['changed_paths'] == ['input_schema'], preview
                assert preview['old_value_sha256'] == observed and preview['new_value_sha256'] == candidate['new_value_sha256']
                assert preview_diff(content, candidate) == preview  # deterministic preview
                # Anything outside the whitelist is refused before anything is built.
                assert 'outside whitelist' in str(refused_build(kind='executable_source',
                    target_artifact_id=old_descriptor, expected_old_value_sha256=observed,
                    observed_old_value_sha256=observed, new_value={'code': 'import os'},
                    criteria_artifact_id=criteria, criteria_sha256=criteria_sha256))
                # A candidate may not replace its own frozen evaluator.
                assert 'candidate may not replace its own evaluator' in str(refused_build(kind='prompt_policy',
                    target_artifact_id=criteria, expected_old_value_sha256=observed,
                    observed_old_value_sha256=observed, new_value={'rules': []},
                    criteria_artifact_id=criteria, criteria_sha256=criteria_sha256))
                # A stale expected old-value hash is refused once the live
                # artifact has moved on.
                replacement_descriptor = await upload(client, actor,
                    {'tool': 'seed.echo', 'input_schema': {'type': 'object', 'title': 'v2'}}, 'tool_descriptor')
                _, current = await load_old_value(client, actor, realm_id=REALM, target_artifact_id=replacement_descriptor)
                assert 'stale expected old value hash' in str(refused_build(kind='tool_descriptor',
                    target_artifact_id=replacement_descriptor, expected_old_value_sha256=observed,
                    observed_old_value_sha256=current, new_value={'tool': 'seed.echo'},
                    criteria_artifact_id=criteria, criteria_sha256=criteria_sha256))
                await refused(load_old_value(client, actor, realm_id=REALM, target_artifact_id=unique('artifact')),
                    'target artifact unavailable')
            finally:
                await client.aclose()
        asyncio.run(run())
