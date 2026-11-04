"""SH-EVO-03 (partial): failure-history trigger → evidence → artifact candidate.

The reachable consumer-side chain on the pinned wheel, composed end to end
on a real daemon: real failing task history read through public bounded
traces fires the bounded trigger policy, the evidence collector turns the
same history into an evidence fixture and an admitted Proposal with
resolvable provenance, and the artifact candidate is built fail-closed
against the live old value under the REPLACE_ARTIFACT whitelist. The chain
then stops honestly before the World gate: no public interface registers
Candidate/World objects on the pinned wheel (RP-06 OPEN), so RunExperiment
and Promote refuse the unregistered references and commit nothing — the
deterministic-experiment and Promotion legs stay out of scope.
"""
import asyncio
import json
import uuid

import pytest

from agent_meta_runtime.sdk import StableError, connect
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.evolution.artifact_candidate import (
    build_candidate, load_old_value, preview_diff)
from agent_meta_seed_harness.evolution.collector import EvidenceCollector
from agent_meta_seed_harness.evolution.tool_trigger import TriggerLimitError, TriggerPolicy
from toolset_runtime import REALM, submit_tools, tools_environment


EVOLUTION_PERMISSIONS = ['artifact.put', 'task.submit', 'model.invoke', 'capability.invoke', 'state.read', 'state.write',
    'experiment.run', 'composition.promote']


def unique(reference_type):
    return f'{reference_type}://019a44d0-0000-7000-8000-{uuid.uuid4().hex[:12]}'


def criteria_document(assertions):
    return {'schema': 'deterministic-evaluation/v1', 'decision_rule': 'ALL_REQUIRED_PASS',
        'assertions': assertions}


def valid_budget_assertion():
    return {'kind': 'budget', 'max_wall_time_us': 1000000, 'max_cost_microunits': 0}


async def upload(client, actor, value, kind):
    return (await client.put_artifact(realm_id=REALM, actor_id=actor.actor_id,
        content=canonical_json(value), kind=kind, media_type='application/json'))['artifact_id']


async def active_composition(client):
    harnesses = await client.list_harnesses()
    return next(item['active_composition_id'] for item in harnesses if item.get('status') == 'ACTIVE')


async def refused(client, command, code, message):
    with pytest.raises(StableError) as caught:
        await command
    assert caught.value.code == code, (caught.value.code, caught.value.message)
    assert message in caught.value.message, caught.value.message


def test_failure_history_triggers_evidence_candidate_and_stops_before_the_world_gate(tmp_path):
    with tools_environment(tmp_path, actor_permissions=EVOLUTION_PERMISSIONS) as (owner, actor, state, replacement):
        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                # Real failure history through the public bounded trace.
                task, terminal, execution = await submit_tools(client, actor,
                    [{'name': 'seed.transform.normalize_json', 'arguments': {'json': 'not-json'}}])
                assert terminal['status'] == 'FAILED' and terminal['error'], terminal
                trace = await client.get_task_trace(task.task_id)

                # The bounded trigger policy fires on the real history and
                # admits exactly one Proposal-window trigger for the target.
                policy = TriggerPolicy(max_proposals_per_window=1, max_candidates_per_window=2,
                    max_experiments_per_window=2, cooldown_us=300_000_000)
                modes = policy.failure_modes([trace])
                assert modes and all(modes.values()), modes
                target_descriptor = await upload(client, actor,
                    {'tool': 'seed.echo', 'input_schema': {'type': 'object'}}, 'tool_descriptor')
                assert policy.register_proposal(window_id='w1', target_path=target_descriptor,
                    now_us=1_000) == policy.digest
                with pytest.raises(TriggerLimitError, match='window exhausted'):
                    policy.register_proposal(window_id='w1', target_path=target_descriptor, now_us=2_000)

                # The same history becomes an evidence fixture and an admitted
                # Proposal whose provenance resolves.
                composition = await active_composition(client)
                result = await EvidenceCollector(client, actor).collect([task.task_id],
                    hypothesis='normalize_json must reject malformed payloads deterministically',
                    target_composition_id=composition)
                ok, reason = await client.verify_artifact(result['evidence_artifact_id'])
                assert ok, reason
                assert result['summary']['tasks'][0]['failure_modes'], result['summary']
                why = await client.why(result['proposal_id'])
                assert why['root_id'] == result['proposal_id'] and result['proposal_id'] in why['nodes'], why

                # The artifact candidate is bound to the live old value under
                # the whitelist with a frozen criteria artifact, and the
                # approval preview is a deterministic canonical diff.
                content, observed = await load_old_value(client, actor, realm_id=REALM,
                    target_artifact_id=target_descriptor)
                criteria_value = criteria_document([valid_budget_assertion()])
                criteria = await upload(client, actor, criteria_value, 'criteria')
                candidate = build_candidate(kind='tool_descriptor', target_artifact_id=target_descriptor,
                    expected_old_value_sha256=observed, observed_old_value_sha256=observed,
                    new_value={'tool': 'seed.echo', 'input_schema': {'type': 'object', 'additionalProperties': False}},
                    criteria_artifact_id=criteria, criteria_sha256=sha256_hex(canonical_json(criteria_value)))
                preview = preview_diff(content, candidate)
                assert preview['changed_paths'] == ['input_schema'], preview
                assert preview['old_value_sha256'] == observed
                assert preview_diff(content, candidate) == preview

                # The chain stops before the World gate: with no public
                # registration interface, RunExperiment and Promote refuse the
                # unregistered references and nothing is committed.
                meta_before = (await client.get_view())['meta_revision']
                refs_before = await client.get_refs()
                await refused(client, client.run_experiment(realm_id=REALM, actor_id=actor.actor_id,
                    candidate_id=unique('candidate'), baseline_id=composition, world_id=unique('world'),
                    criteria_artifact_id=criteria), 'NOT_FOUND', 'world not found')
                await refused(client, client.promote_candidate(realm_id=REALM, actor_id=actor.actor_id,
                    candidate_id=unique('candidate'), evaluation_id=unique('evaluation')),
                    'NOT_FOUND', 'candidate not found')
                assert (await client.get_view())['meta_revision'] == meta_before
                assert await client.get_refs() == refs_before
            finally:
                await client.aclose()
        asyncio.run(run())
