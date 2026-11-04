"""SH-EVO-05 (partial): defect history → code candidate → S03 gates → operator activation.

A code-level defect observed in real task history triggers a bounded code
candidate: the candidate source tree is generated once through the frozen
budget and isolated-tree discipline, its bundle provenance is bound to that
tree, and it walks the exact S03 release path — validate, install into its
own slot, operator-signed activation (the agent cannot produce a valid
activation envelope), frozen old-task drain, a failed candidate that never
realizes, and a rollback that is a fresh approved activation whose receipt
replays identically after an owner restart. Candidate/World/Experiment
registration has no public interface on the pinned wheel (RP-06 OPEN), so
the evidence-driven generation pipeline upstream of the candidate tree stays
out of scope.
"""
import asyncio
from importlib.resources import files
import json
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.evolution.code_release import CandidateStaging
from agent_meta_seed_harness.evolution.package_candidate import (
    CODE_BUDGET_CEILING, CandidateBudget, CodeCandidateError)
from agent_meta_seed_harness.evolution.tool_trigger import TriggerPolicy
from agent_meta_seed_harness.packaging import EXECUTION_SOURCE_PATHS
from recovery_runtime import terminal_execution, wait_invocations
from seed_actor import create_actor
from seed_package import activate_seed, install_seed, seed_bundle, wait_ready
from seed_runtime import admin, daemon_process, invoke

REALM = 'realm://main'
PERMISSIONS = ['artifact.put', 'task.submit', 'model.invoke', 'capability.invoke', 'state.read', 'state.write',
    'scratch.create', 'scratch.execute', 'scratch.inspect', 'scratch.export', 'scratch.release']

PROVIDER = b'''
import asyncio
import json
from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import JsonPart, ModelResponse, ProviderUsage, ToolCallPart
from agent_meta_runtime.sdk.packages import canonical_json

async def invoke_fake(request):
    if request.ordinal == 0:
        return ModelResponse((ToolCallPart("echo-0", "seed.echo", canonical_json({"value": "__PACKAGE_VERSION__"}).decode()),), "TOOL_CALL", ProviderUsage(None, None, 0))
    history = json.loads(request.history_content)
    assert json.loads(bytes.fromhex(history[1]["content_hex"])) == {"value": "__PACKAGE_VERSION__"}
    return ModelResponse((JsonPart({"package_version": "__PACKAGE_VERSION__"}),), "STOP", ProviderUsage(None, None, 0))
'''

LOOP_DEFECT = b'''
import asyncio
import json
from agent_meta_runtime.sdk.host import ToolCallPart, terminal_result
from .context import project

async def run_task(task, host):
    scenario = json.loads(task.input_content)["scenario"]
    if scenario == "defect":
        raise RuntimeError("v1 defect: unguarded retry")
    if scenario == "slow":
        await asyncio.sleep(4)
    response = await host.invoke_model(await project(task, host))
    for call in response.parts:
        if isinstance(call, ToolCallPart):
            await host.invoke_tool(call)
    response = await host.invoke_model(await project(task, host))
    return terminal_result(response)
'''

LOOP_FIXED = LOOP_DEFECT.replace(
    b'    if scenario == "defect":\n        raise RuntimeError("v1 defect: unguarded retry")\n', b'')


def provider(version):
    return PROVIDER.replace(b'__PACKAGE_VERSION__', version if isinstance(version, bytes) else version.encode())


def live_tree():
    return {name: files('agent_meta_seed_harness').joinpath(name.split('/', 1)[1]).read_bytes()
        for name in EXECUTION_SOURCE_PATHS}


def tree_identity(tree):
    return sha256_hex(canonical_json({'sources': {path: sha256_hex(raw) for path, raw in sorted(tree.items())}}))


def unhealthy_binding():
    binding = files('agent_meta_seed_harness').joinpath('host_binding.py').read_bytes()
    assert b'HealthStatus("READY", "OFFLINE_ADAPTER_READY")' in binding
    return binding.replace(b'HealthStatus("READY", "OFFLINE_ADAPTER_READY")',
        b'HealthStatus("UNHEALTHY", "SELF_TEST_FAILED")')


def v1_pair():
    bundle, publisher = seed_bundle(version='0.1.0-dev.1', descriptor_revision=1,
        overrides={'agent_meta_seed_harness/loop.py': LOOP_DEFECT,
            'agent_meta_seed_harness/providers/fake.py': provider(b'0.1.0-dev.1')})
    return bundle, publisher


def v1_tree():
    return {**live_tree(), 'agent_meta_seed_harness/loop.py': LOOP_DEFECT,
        'agent_meta_seed_harness/providers/fake.py': provider(b'0.1.0-dev.1')}


def candidate(revision, *, base_tree, previous, budget, day, overrides=None, defect_loop=False):
    """Generate one candidate through the explicit staging pass and return
    (tree, bundle) with provenance bound to the isolated tree."""
    version = f'0.1.{revision - 1}-dev.1'
    changes = {'agent_meta_seed_harness/loop.py': LOOP_DEFECT if defect_loop else LOOP_FIXED,
        'agent_meta_seed_harness/providers/fake.py': provider(f'0.1.{revision - 1}-dev.1')}
    if overrides:
        changes.update(overrides)
    staging = CandidateStaging(budget)
    tree = staging.generate(day=day, generation_tokens=10_000, base_sources=base_tree,
        overrides=changes, version=version, descriptor_revision=revision, previous=previous)
    root = Path(__file__).resolve().parents[2]
    bundle, _publisher = seed_bundle(version=version, descriptor_revision=revision,
        overrides={path: raw for path, raw in changes.items() if base_tree.get(path) != raw})
    staging.bind(bundle, dependency_lock=(root / 'requirements-ci.lock').read_bytes(),
        contract_bundle_sha256=sha256_hex((root / 'docs/runtime-contract/manifest.json').read_bytes()))
    return tree, bundle, staging


async def submit(client, actor, scenario):
    reference = (await client.put_artifact(realm_id=REALM, actor_id=actor.actor_id,
        content=canonical_json({'provider': 'fake', 'scenario': scenario, 'value': 'fixture'}),
        kind='task_input', media_type='application/json'))['artifact_id']
    task = await client.submit_task(realm_id=REALM, actor_id=actor.actor_id, input_artifact_id=reference)
    return task.task_id


async def submit_under(data_dir, actor, scenario):
    client = await connect(data_dir, authority=actor)
    try:
        return await submit(client, actor, scenario)
    finally:
        await client.aclose()


async def refs_at(data_dir, *, serving, status=None):
    client = await connect(data_dir)
    try:
        end = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < end:
            refs = await client.get_refs()
            if refs['serving_revision'] == serving and (status is None or refs['reconcile_status'] == status):
                return refs
            await asyncio.sleep(.01)
        raise AssertionError(f'cutover did not reach the requested state: {refs}')
    finally:
        await client.aclose()


def assert_result(result, execution, *, version):
    from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, encode_terminal_result
    assert result['status'] == 'SUCCEEDED', result
    expected = TerminalResult((JsonPart({'package_version': version}),))
    assert result['result_artifact_id'] == 'artifact://sha256/' + sha256_hex(encode_terminal_result(expected))


def test_defect_history_candidate_reaches_serving_through_full_gates(tmp_path):
    first, publisher = v1_pair()
    budget = CandidateBudget(**CODE_BUDGET_CEILING)
    base = v1_tree()
    v2_tree, second, v2_staging = candidate(2, base_tree=base,
        previous={'version': '0.1.0-dev.1', 'content_sha256': tree_identity(base), 'descriptor_revision': 1},
        budget=budget, day='2026-11-04')
    # The staging pass is single-pass: re-entering generate or binding before
    # generating is a terminal error, never a retry.
    with pytest.raises(CodeCandidateError, match='staging is single-pass'):
        v2_staging.generate(day='2026-11-06', generation_tokens=10_000, base_sources=base,
            overrides={}, version='0.1.9-dev.9', descriptor_revision=9, previous=None)
    with pytest.raises(CodeCandidateError, match='bind requires a completed generate stage'):
        CandidateStaging(budget).bind(second, dependency_lock=b'x', contract_bundle_sha256='0' * 64)
    # The exhausted day is terminal — nothing reopens the budget or schedules
    # a retry; there is no resident evolution loop.
    for _ in range(2):
        with pytest.raises(CodeCandidateError, match='candidate budget exhausted'):
            CandidateStaging(budget).generate(day='2026-11-04', generation_tokens=10_000,
                base_sources=base, overrides={}, version='0.1.9-dev.9', descriptor_revision=9, previous=None)
    v3_tree, failed, _v3_staging = candidate(3, base_tree=v2_tree,
        previous={'version': '0.1.1-dev.1', 'content_sha256': tree_identity(v2_tree), 'descriptor_revision': 2},
        budget=budget, day='2026-11-05',
        overrides={'agent_meta_seed_harness/host_binding.py': unhealthy_binding()}, defect_loop=True)

    with daemon_process(tmp_path, publishers=[publisher]) as owner:
        data_dir = owner.data_dir
        actor = create_actor(data_dir, permissions=PERMISSIONS)
        old_id = install_seed(data_dir, tmp_path, first)
        asyncio.run(wait_ready(data_dir, revision=1))

        async def history():
            client = await connect(data_dir, authority=actor)
            try:
                defect_task = await submit(client, actor, 'defect')
                terminal, done = await client.wait_task(defect_task, timeout_s=15)
                assert done and terminal['status'] == 'FAILED', terminal
                trace = await client.get_task_trace(defect_task)
                modes = TriggerPolicy(max_proposals_per_window=1, max_candidates_per_window=2,
                    max_experiments_per_window=2, cooldown_us=300_000_000).failure_modes([trace])
                assert modes, trace
                return await submit(client, actor, 'slow')
            finally:
                await client.aclose()
        slow_task = asyncio.run(history())
        frozen = asyncio.run(wait_invocations(data_dir, slow_task,
            statuses=['SUCCEEDED', 'SUCCEEDED', 'SUCCEEDED']))

        candidate_id = install_seed(data_dir, tmp_path, second, activate=False)
        failed_id = install_seed(data_dir, tmp_path, failed, activate=False)
        manifest = json.loads(second.artifacts[second.manifest_artifact_id])
        # The agent holds no signing material: an envelope without the
        # package's exact signed grant requests is refused, committing nothing.
        bad, envelope = invoke(data_dir, 'harness', 'activate', candidate_id,
            manifest['composition_template_artifact_id'])
        assert bad.returncode != 0 and envelope['error']['code'] == 'AUTHORITY_DENIED', envelope
        fabricated, envelope = invoke(data_dir, 'harness', 'activate', candidate_id,
            manifest['composition_template_artifact_id'], '--grant', canonical_json(
                {'permission': 'model.invoke', 'scope': {'realm_id': REALM,
                    'targets': [{'type': 'CAPABILITY', 'id': 'capability://seed.fake-model'}]}}).decode())
        assert fabricated.returncode != 0 and envelope['error']['code'] == 'AUTHORITY_DENIED', envelope
        assert admin(data_dir, 'refs')['serving_revision'] == 1

        # Operator-signed activation cuts serving over; the frozen old task
        # drains under its frozen composition and keeps the old version. The
        # activation envelope is assembled from the staging module's plain
        # activation inputs — the generator itself never signs anything.
        inputs = v2_staging.activation_inputs(second)
        assert (inputs['name'], inputs['version']) == (manifest['package_name'], manifest['package_version'])
        grant_flags = [value for request in inputs['grant_requests']
            for value in ('--grant', canonical_json(request).decode())]
        admin(data_dir, 'harness', 'activate', candidate_id,
            inputs['composition_template_artifact_id'], *grant_flags)
        asyncio.run(refs_at(data_dir, serving=2, status='READY'))
        asyncio.run(wait_ready(data_dir, revision=2))
        result, execution = asyncio.run(terminal_execution(data_dir, slow_task))
        assert_result(result, execution, version='0.1.0-dev.1')
        assert execution['serving_composition_id'] == frozen['serving_composition_id']
        assert execution['accepted_meta_revision'] == frozen['accepted_meta_revision']
        assert admin(data_dir, 'harness', 'inspect', old_id)['status'] == 'INACTIVE'

        cured_task = asyncio.run(submit_under(data_dir, actor, 'defect'))
        cured_result, cured_execution = asyncio.run(terminal_execution(data_dir, cured_task))
        assert_result(cured_result, cured_execution, version='0.1.1-dev.1')

        # The unhealthy candidate is installed but its activation never
        # realizes; serving stays on the healthy candidate.
        activate_seed(data_dir, failed, failed_id)
        refs = asyncio.run(refs_at(data_dir, serving=2, status='FAILED'))
        assert refs['desired_revision'] == 3 and refs['realized_revision'] == 2, refs
        asyncio.run(wait_ready(data_dir, revision=2))
        assert admin(data_dir, 'harness', 'inspect', candidate_id)['status'] == 'ACTIVE'
        assert admin(data_dir, 'harness', 'inspect', failed_id)['status'] == 'INSTALLED'
        still_task = asyncio.run(submit_under(data_dir, actor, 'defect'))
        still_result, still_execution = asyncio.run(terminal_execution(data_dir, still_task))
        assert_result(still_result, still_execution, version='0.1.1-dev.1')
        assert still_execution['serving_composition_id'] == cured_execution['serving_composition_id']


def test_candidate_rollback_is_a_fresh_approved_activation_that_replays_after_restart(tmp_path):
    first, publisher = v1_pair()
    budget = CandidateBudget(**CODE_BUDGET_CEILING)
    _, second, _staging = candidate(2, base_tree=v1_tree(),
        previous={'version': '0.1.0-dev.1', 'content_sha256': tree_identity(v1_tree()), 'descriptor_revision': 1},
        budget=budget, day='2026-11-04')
    method = 'agent_meta.public.v1.Harness.Activate'
    with daemon_process(tmp_path, publishers=[publisher], label='before-rollback') as owner:
        data_dir = owner.data_dir
        actor = create_actor(data_dir, permissions=PERMISSIONS)
        old_id = install_seed(data_dir, tmp_path, first, activate=False)
        activate_seed(data_dir, first, old_id)
        asyncio.run(wait_ready(data_dir, revision=1))
        served_task = asyncio.run(submit_under(data_dir, actor, 'normal'))
        served_result, served_execution = asyncio.run(terminal_execution(data_dir, served_task))
        assert_result(served_result, served_execution, version='0.1.0-dev.1')
        candidate_id = install_seed(data_dir, tmp_path, second, activate=False)
        activate_seed(data_dir, second, candidate_id)
        asyncio.run(wait_ready(data_dir, revision=2))
        upgraded_task = asyncio.run(submit_under(data_dir, actor, 'normal'))
        upgraded_result, upgraded_execution = asyncio.run(terminal_execution(data_dir, upgraded_task))
        assert_result(upgraded_result, upgraded_execution, version='0.1.1-dev.1')

        # Rollback is a fresh approved operator activation of the old package.
        manifest = json.loads(first.artifacts[first.manifest_artifact_id])
        requests = json.loads(first.artifacts[manifest['grant_requests_artifact_id']])['requests']
        flags = [value for request in requests for value in ('--grant', canonical_json(request).decode())]
        envelope = admin(data_dir, '--dry-run', 'harness', 'activate', old_id,
            manifest['composition_template_artifact_id'], *flags)['command_envelope_jcs']

        async def rollback():
            client = await connect(data_dir)
            try:
                return await client.execute_command(method, envelope)
            finally:
                await client.aclose()
        resource = asyncio.run(rollback()).resource
        asyncio.run(wait_ready(data_dir, revision=3))
        assert resource['revision'] == 3
        assert admin(data_dir, 'harness', 'inspect', old_id)['status'] == 'ACTIVE'
        assert admin(data_dir, 'harness', 'inspect', candidate_id)['status'] == 'INACTIVE'
        rolled_task = asyncio.run(submit_under(data_dir, actor, 'normal'))
        rolled_result, rolled_execution = asyncio.run(terminal_execution(data_dir, rolled_task))
        assert_result(rolled_result, rolled_execution, version='0.1.0-dev.1')
        preserved_result, _ = asyncio.run(terminal_execution(data_dir, served_task))
        assert preserved_result['result_artifact_id'] == served_result['result_artifact_id']

    with daemon_process(tmp_path, publishers=[publisher], label='after-rollback') as owner:
        data_dir = owner.data_dir
        asyncio.run(wait_ready(data_dir, revision=3))

        async def replay():
            client = await connect(data_dir)
            try:
                first_replay = await client.execute_command(method, envelope)
                second_replay = await client.execute_command(method, envelope)
                return first_replay, second_replay
            finally:
                await client.aclose()
        first_replay, second_replay = asyncio.run(replay())
        assert first_replay.resource == second_replay.resource == resource
        after_task = asyncio.run(submit_under(data_dir, actor, 'normal'))
        after_result, after_execution = asyncio.run(terminal_execution(data_dir, after_task))
        assert_result(after_result, after_execution, version='0.1.0-dev.1')
