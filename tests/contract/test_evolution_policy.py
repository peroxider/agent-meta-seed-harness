"""S07 evolution admission: fail-closed references, no auto-creation, no serving drift.

The plan forbids assuming ``run_experiment`` auto-creates missing objects, or
passing an ArtifactId off as a CandidateId. Every command here uses only the
public SDK against a real daemon; a refusal must commit no object (meta
revision unchanged) and must never move serving.
"""
import asyncio
import json
import uuid

import pytest

from agent_meta_runtime.sdk import StableError, connect
from seed_actor import create_actor
from toolset_runtime import REALM, tools_environment


EVOLUTION_PERMISSIONS = ['artifact.put', 'capability.invoke', 'state.read', 'state.write',
    'experiment.run', 'composition.promote']


def unique(reference_type):
    return f'{reference_type}://019a44d0-0000-7000-8000-{uuid.uuid4().hex[:12]}'


def criteria_document(assertions):
    return {'schema': 'deterministic-evaluation/v1', 'decision_rule': 'ALL_REQUIRED_PASS',
        'assertions': assertions}


async def refused(client, command, code, message):
    with pytest.raises(StableError) as caught:
        await command
    assert caught.value.code == code, (caught.value.code, caught.value.message)
    assert message in caught.value.message, caught.value.message
    return caught.value


def valid_budget_assertion():
    return {'kind': 'budget', 'max_wall_time_us': 1000000, 'max_cost_microunits': 0}


async def upload_criteria(client, actor, document):
    put = await client.put_artifact(realm_id=REALM, actor_id=actor.actor_id,
        content=json.dumps(document).encode('utf-8'), kind='criteria', media_type='application/json')
    return put['artifact_id']


def test_evolution_admission_refuses_unregistered_references_without_state_change(tmp_path):
    with tools_environment(tmp_path, actor_permissions=EVOLUTION_PERMISSIONS) as (owner, actor, state, replacement):
        data = owner.data_dir
        async def run():
            client = await connect(data, authority=actor)
            try:
                composition = unique('composition')
                world = unique('world')
                candidate = unique('candidate')
                fabricated_criteria = unique('artifact')
                real_criteria = await upload_criteria(client, actor, criteria_document([valid_budget_assertion()]))
                broken_criteria = await upload_criteria(client, actor, criteria_document([]))
                before = await client.get_refs()
                meta_before = (await client.get_view())['meta_revision']

                # Evolution.Propose: the target Composition must exist; nothing
                # is auto-created and no Proposal object is committed.
                await refused(client, client.propose(realm_id=REALM, actor_id=actor.actor_id,
                    hypothesis='fabricated target', target_composition_id=composition,
                    source_evidence_ids=[unique('fact')]), 'NOT_FOUND', 'target composition not found')

                # Evolution.RunExperiment refuses in declared order: unknown
                # criteria ArtifactId, malformed criteria document, then the
                # unregistered World. No Experiment object is created for any
                # refusal, and an ArtifactId passed as candidate_id never gets
                # past admission.
                await refused(client, client.run_experiment(realm_id=REALM, actor_id=actor.actor_id,
                    candidate_id=candidate, baseline_id=composition, world_id=world,
                    criteria_artifact_id=fabricated_criteria), 'NOT_FOUND', 'unknown artifact')
                invalid = await refused(client, client.run_experiment(realm_id=REALM, actor_id=actor.actor_id,
                    candidate_id=candidate, baseline_id=composition, world_id=world,
                    criteria_artifact_id=broken_criteria), 'INVALID_ARGUMENT', 'invalid evaluation criteria document')
                assert 'criteria.assertions' in invalid.details['issues'], invalid.details
                await refused(client, client.run_experiment(realm_id=REALM, actor_id=actor.actor_id,
                    candidate_id=candidate, baseline_id=composition, world_id=world,
                    criteria_artifact_id=real_criteria), 'NOT_FOUND', 'world not found')
                await refused(client, client.run_experiment(realm_id=REALM, actor_id=actor.actor_id,
                    candidate_id=real_criteria, baseline_id=composition, world_id=world,
                    criteria_artifact_id=real_criteria), 'NOT_FOUND', 'world not found')

                # Evolution.Promote: unregistered candidates — including an
                # ArtifactId in the CandidateId position — are refused and no
                # promotion path exists without a registered Candidate.
                await refused(client, client.promote_candidate(realm_id=REALM, actor_id=actor.actor_id,
                    candidate_id=candidate, evaluation_id=unique('evaluation')), 'NOT_FOUND', 'candidate not found')
                await refused(client, client.promote_candidate(realm_id=REALM, actor_id=actor.actor_id,
                    candidate_id=real_criteria, evaluation_id=unique('evaluation')), 'NOT_FOUND', 'candidate not found')

                await refused(client, client.get_experiment(unique('experiment')), 'NOT_FOUND', 'experiment not found')

                # Every refusal committed nothing: identical refs, identical
                # meta revision — no proposal, experiment, candidate or world
                # was auto-created, and serving never moved.
                after = await client.get_refs()
                assert after == before, (before, after)
                assert (await client.get_view())['meta_revision'] == meta_before
            finally:
                await client.aclose()
        asyncio.run(run())


def test_evolution_propose_on_real_composition_admits_provenance_without_serving_change(tmp_path):
    with tools_environment(tmp_path, actor_permissions=EVOLUTION_PERMISSIONS) as (owner, actor, state, replacement):
        data = owner.data_dir
        async def run():
            client = await connect(data, authority=actor)
            try:
                harnesses = await client.list_harnesses()
                composition = next(item['active_composition_id'] for item in harnesses
                    if item.get('status') == 'ACTIVE')
                before = await client.get_refs()
                result = await client.propose(realm_id=REALM, actor_id=actor.actor_id,
                    hypothesis='real-target admission probe', target_composition_id=composition,
                    source_evidence_ids=[])
                proposal_id = result.resource['proposal_id']
                assert proposal_id.startswith('proposal://'), result.resource
                why = await client.why(proposal_id)
                assert why['root_id'] == proposal_id and proposal_id in why['nodes'], why
                after = await client.get_refs()
                assert after == before, (before, after)
            finally:
                await client.aclose()
        asyncio.run(run())


def test_evolution_commands_require_experiment_run_authority(tmp_path):
    with tools_environment(tmp_path, actor_permissions=EVOLUTION_PERMISSIONS) as (owner, actor, state, replacement):
        data = owner.data_dir
        unauthorized = create_actor(data, permissions=['artifact.put'])
        async def run():
            client = await connect(data, authority=actor)
            denied = await connect(data, authority=unauthorized)
            try:
                meta_before = (await client.get_view())['meta_revision']
                await refused(denied, denied.propose(realm_id=REALM, actor_id=unauthorized.actor_id,
                    hypothesis='unauthorized', target_composition_id=unique('composition')), 'AUTHORITY_DENIED', '')
                await refused(denied, denied.run_experiment(realm_id=REALM, actor_id=unauthorized.actor_id,
                    candidate_id=unique('candidate'), baseline_id=unique('composition'),
                    world_id=unique('world'), criteria_artifact_id=unique('artifact')), 'AUTHORITY_DENIED', '')
                await refused(denied, denied.promote_candidate(realm_id=REALM, actor_id=unauthorized.actor_id,
                    candidate_id=unique('candidate'), evaluation_id=unique('evaluation')), 'AUTHORITY_DENIED', '')
                assert (await client.get_view())['meta_revision'] == meta_before
            finally:
                await client.aclose()
                await denied.aclose()
        asyncio.run(run())
