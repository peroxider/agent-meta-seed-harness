"""SH-EVO-01 (partial): real history → evidence fixture → Proposal, public only.

The pinned Runtime records ``source_evidence_ids`` as opaque strings and has
no public registration interface for Candidate/World/Experiment (RP-06 OPEN),
so the provable pipeline bound on this wheel is the collector leg: task
history read through public bounded traces is aggregated into an evidence
fixture and a Proposal whose references resolve fail-closed — refusals commit
nothing and never fabricate a pass.
"""
import asyncio
import uuid

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_seed_harness.evolution.collector import EvidenceCollector, InsufficientEvidence
from toolset_runtime import submit_tools, tools_environment


EVOLUTION_PERMISSIONS = ['artifact.put', 'task.submit', 'model.invoke', 'capability.invoke', 'state.read', 'state.write',
    'experiment.run', 'composition.promote']


def unique(reference_type):
    return f'{reference_type}://019a44d0-0000-7000-8000-{uuid.uuid4().hex[:12]}'


async def active_composition(client):
    harnesses = await client.list_harnesses()
    return next(item['active_composition_id'] for item in harnesses if item.get('status') == 'ACTIVE')


def test_collector_builds_proposal_from_real_history_with_resolvable_provenance(tmp_path):
    with tools_environment(tmp_path, actor_permissions=EVOLUTION_PERMISSIONS) as (owner, actor, state, replacement):
        data = owner.data_dir
        async def run():
            client = await connect(data, authority=actor)
            try:
                task, terminal, execution = await submit_tools(client, actor,
                    [{'name': 'seed.echo', 'arguments': {'value': 'evidence'}}])
                assert terminal['status'] == 'SUCCEEDED', terminal
                composition = await active_composition(client)
                result = await EvidenceCollector(client, actor).collect([task.task_id],
                    hypothesis='probe admission', target_composition_id=composition)
                # The evidence fixture is committed and content-addressed.
                ok, reason = await client.verify_artifact(result['evidence_artifact_id'])
                assert ok, reason
                # Every evidence reference resolves: fact ids appear in the
                # real task trace, the fixture is in the Artifact store.
                trace = await client.get_task_trace(task.task_id)
                observed = {edge['source_fact_id'] for edge in trace['edges']}
                for reference in result['source_evidence_ids']:
                    assert reference == result['evidence_artifact_id'] or reference in observed, reference
                assert result['summary']['tasks'][0]['task_id'] == task.task_id
                assert result['summary']['source_fact_ids'] and all(
                    reference in observed for reference in result['summary']['source_fact_ids'])
                # The admitted Proposal's provenance resolves.
                why = await client.why(result['proposal_id'])
                assert why['root_id'] == result['proposal_id'] and result['proposal_id'] in why['nodes'], why
            finally:
                await client.aclose()
        asyncio.run(run())


def test_collector_exits_insufficient_evidence_without_fabricating(tmp_path):
    with tools_environment(tmp_path, actor_permissions=EVOLUTION_PERMISSIONS) as (owner, actor, state, replacement):
        data = owner.data_dir
        async def run():
            client = await connect(data, authority=actor)
            try:
                task, terminal, execution = await submit_tools(client, actor,
                    [{'name': 'seed.echo', 'arguments': {'value': 'refusal'}}])
                composition = await active_composition(client)
                meta_before = (await client.get_view())['meta_revision']
                refs_before = await client.get_refs()
                collector = EvidenceCollector(client, actor)

                async def refused(collect, message):
                    with pytest.raises(InsufficientEvidence) as caught:
                        await collect
                    assert message in str(caught.value), caught.value

                await refused(collector.collect([], hypothesis='empty history',
                    target_composition_id=composition), 'no task history')
                await refused(collector.collect([unique('task')], hypothesis='unknown task',
                    target_composition_id=composition), 'task history unavailable')
                await refused(collector.collect([task.task_id], hypothesis='fabricated fact',
                    target_composition_id=composition, additional_evidence_ids=[unique('fact')]),
                    'not in observed history')
                await refused(collector.collect([task.task_id], hypothesis='fabricated artifact',
                    target_composition_id=composition, additional_evidence_ids=[unique('artifact')]),
                    'artifact evidence unavailable')
                await refused(collector.collect([task.task_id], hypothesis='unknown scheme',
                    target_composition_id=composition, additional_evidence_ids=[unique('nonsense')]),
                    'not in observed history')

                # Nothing was committed: no evidence fixture, no Proposal, and
                # serving never moved.
                assert (await client.get_view())['meta_revision'] == meta_before, (meta_before,)
                assert await client.get_refs() == refs_before
            finally:
                await client.aclose()
        asyncio.run(run())
