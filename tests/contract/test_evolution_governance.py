"""SH-GOV-01 (partial): conditional meta/serving revisions and Evolution authority.

Only the publicly reachable governance legs of the pinned wheel are pinned
here: `Evolution.Propose` honors a caller-observed `expected_meta_revision`
(stale observations refuse `REVISION_CONFLICT` and commit nothing),
`Evolution.Rollback` requires the `composition.rollback` permission and
refuses fabricated parents and stale serving observations — no object is
auto-created and serving never moves. The fixed adjudicator and signed
binding are Runtime-internal on this wheel and stay unpinned.
"""
import asyncio
import uuid

import pytest

from agent_meta_runtime.sdk import StableError, connect
from seed_actor import create_actor
from toolset_runtime import REALM, tools_environment


EVOLUTION_PERMISSIONS = ['artifact.put', 'task.submit', 'model.invoke', 'capability.invoke', 'state.read', 'state.write',
    'experiment.run', 'composition.promote', 'composition.rollback']


def unique(reference_type):
    return f'{reference_type}://019a44d0-0000-7000-8000-{uuid.uuid4().hex[:12]}'


async def refused(client, command, code, message):
    with pytest.raises(StableError) as caught:
        await command
    assert caught.value.code == code, (caught.value.code, caught.value.message)
    assert message in caught.value.message, caught.value.message
    return caught.value


async def active_composition(client):
    harnesses = await client.list_harnesses()
    return next(item['active_composition_id'] for item in harnesses if item.get('status') == 'ACTIVE')


def test_propose_honors_expected_meta_revision_and_refusals_commit_nothing(tmp_path):
    with tools_environment(tmp_path, actor_permissions=EVOLUTION_PERMISSIONS) as (owner, actor, state, replacement):
        data = owner.data_dir
        async def run():
            client = await connect(data, authority=actor)
            try:
                composition = await active_composition(client)
                refs_before = await client.get_refs()
                observed = (await client.get_view())['meta_revision']
                # A proposal conditioned on the caller's observed revision is
                # admitted; the observation then becomes stale.
                result = await client.propose(realm_id=REALM, actor_id=actor.actor_id,
                    hypothesis='conditioned on observed meta revision', target_composition_id=composition,
                    source_evidence_ids=[], expected_meta_revision=observed)
                assert result.resource['proposal_id'].startswith('proposal://'), result.resource
                # The stale observation refuses and commits nothing.
                conflict = await refused(client, client.propose(realm_id=REALM, actor_id=actor.actor_id,
                    hypothesis='conditioned on stale meta revision', target_composition_id=composition,
                    source_evidence_ids=[], expected_meta_revision=observed), 'REVISION_CONFLICT',
                    'command expected meta revision differs')
                assert conflict.details['expected'] == observed and conflict.details['actual'] > observed, conflict.details
                assert (await client.get_view())['meta_revision'] == observed + 1
                assert await client.get_refs() == refs_before
            finally:
                await client.aclose()
        asyncio.run(run())


def test_rollback_requires_authority_and_refuses_fabricated_or_stale_targets(tmp_path):
    with tools_environment(tmp_path, actor_permissions=EVOLUTION_PERMISSIONS) as (owner, actor, state, replacement):
        data = owner.data_dir
        unauthorized = create_actor(data, permissions=['artifact.put', 'experiment.run', 'composition.promote'])
        async def run():
            client = await connect(data, authority=actor)
            denied = await connect(data, authority=unauthorized)
            try:
                composition = await active_composition(client)
                refs_before = await client.get_refs()
                meta_before = (await client.get_view())['meta_revision']
                # The `composition.rollback` permission gates the command.
                await refused(denied, denied.rollback_composition(realm_id=REALM,
                    actor_id=unauthorized.actor_id, target_parent_id=unique('composition'),
                    expected_serving_revision=0), 'AUTHORITY_DENIED', 'command authority rejected')
                # An authorized rollback cannot invent a parent composition.
                await refused(client, client.rollback_composition(realm_id=REALM, actor_id=actor.actor_id,
                    target_parent_id=unique('composition'), expected_serving_revision=0),
                    'NOT_FOUND', 'rollback target composition not found')
                # A stale serving observation refuses and commits nothing.
                serving = (await client.get_refs())['serving_revision']
                await refused(client, client.rollback_composition(realm_id=REALM, actor_id=actor.actor_id,
                    target_parent_id=composition, expected_serving_revision=serving + 5),
                    'REVISION_CONFLICT', 'serving revision changed since observation')
                assert (await client.get_view())['meta_revision'] == meta_before
                assert await client.get_refs() == refs_before
            finally:
                await client.aclose()
                await denied.aclose()
        asyncio.run(run())
