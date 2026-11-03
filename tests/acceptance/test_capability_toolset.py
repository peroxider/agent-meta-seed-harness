"""Development tools integration; independent Scratch/S05 gates remain OPEN."""
import asyncio
import json
from importlib.resources import files

from agent_meta_runtime.sdk import connect
from toolset_runtime import REALM, tools_environment, submit_tools, upload
from seed_package import seed_bundle
from seed_runtime import daemon_process


def test_signed_tools_use_public_resources_frozen_reads_cas_overlay_and_redaction(tmp_path):
    with tools_environment(tmp_path) as (owner, actor, state, replacement):
        data = owner.data_dir
        async def run():
            client = await connect(data, authority=actor)
            try:
                calls = [
                    {'name':'seed.artifact.read','arguments':{'artifact_id':state['content_artifact_id']}},
                    {'name':'seed.artifact.put','arguments':{'value':{'answer':42,'secret':'TOOLS_CANARY'}}},
                    {'name':'seed.state.read','arguments':{'state_id':state['state_id']}},
                    {'name':'seed.state.write','arguments':{'state_id':state['state_id'],
                        'expected_state_revision_id':state['state_revision_id'],'content_artifact_id':replacement}},
                    {'name':'seed.state.read','arguments':{'state_id':state['state_id']}},
                    {'name':'seed.transform.normalize_json','arguments':{'json':' {"z":2,"secret":"TRANSFORM_CANARY","a":1} '}},
                ]
                task, terminal, execution = await submit_tools(client, actor, calls)
                assert terminal['status'] == 'SUCCEEDED', terminal
                invocations = execution['invocations']
                assert [row['kind'] for row in invocations] == ['MODEL', *(['CAPABILITY'] * 6), 'MODEL']
                results = [json.loads(await client.get_artifact_content(row['output_artifact_id'])) for row in invocations[1:-1]]
                assert results[0]['content']['value'] == {'value':1}
                assert json.loads(await client.get_artifact_content(results[1]['artifact_id'])) == {'answer':42,'secret':'[REDACTED]'}
                assert results[2]['value'] == {'value':1}
                assert results[3]['state_revision_id'] == results[4]['state_revision_id']
                assert results[4]['value'] == {'value':2}
                assert results[5] == {'value':{'a':1,'secret':'[REDACTED]','z':2}}
                current = await client.get_state(realm_id=REALM, actor_id=actor.actor_id, state_id=state['state_id'])
                assert current['cas_revision'] == 2 and current['state_revision_id'] == results[3]['state_revision_id']
                assert execution['consumed_budget']['steps'] == 8 and execution['consumed_budget']['effects'] == 4
                trace = await client.get_task_trace(task.task_id)
                for row in invocations[1:-1]:
                    assert row['action_id'] != execution['root_action_id']
                    assert any(edge['edge_type']=='caused_by' and edge['from_id']==row['action_id'] and
                        edge['to_id']==execution['root_action_id'] for edge in trace['edges'])
                second_task, second_terminal, second = await submit_tools(client, actor, [calls[-1]])
                assert second_terminal['status'] == 'SUCCEEDED'
                assert second['invocations'][1]['output_artifact_id'] == invocations[6]['output_artifact_id']
            finally:
                await client.aclose()
        asyncio.run(run())


def test_confirmed_state_tool_survives_owned_process_kill_without_second_write(tmp_path):
    original = files('agent_meta_seed_harness').joinpath('loop.py').read_bytes()
    override = b'import asyncio\n' + original.replace(b'result = await host.invoke_tool(call)',
        b'result = await host.invoke_tool(call)\n            await asyncio.sleep(1)')
    overrides = {'agent_meta_seed_harness/loop.py':override}
    with tools_environment(tmp_path, overrides=overrides) as (owner, actor, state, replacement):
        async def kill_after_confirmation():
            client = await connect(owner.data_dir, authority=actor)
            try:
                reference = await upload(client, actor, {'provider':'fake-tools','calls':[{'name':'seed.state.write',
                    'arguments':{'state_id':state['state_id'],'expected_state_revision_id':state['state_revision_id'],
                        'content_artifact_id':replacement}}]}, 'task_input')
                task = await client.submit_task(realm_id=REALM, actor_id=actor.actor_id, input_artifact_id=reference)
                end = asyncio.get_running_loop().time() + 10
                while asyncio.get_running_loop().time() < end:
                    execution = await client.get_task_execution(task.task_id)
                    tools = [row for row in execution['invocations'] if row['kind'] == 'CAPABILITY' and row['status'] == 'SUCCEEDED']
                    if tools:
                        assert len(execution['invocations']) == 2
                        confirmed = tools[0]
                        owner.process.kill()
                        owner.process.wait(timeout=10)
                        return task, confirmed
                    await asyncio.sleep(.01)
                raise AssertionError('State tool confirmation deadline exceeded')
            finally:
                await client.aclose()
        task, confirmed = asyncio.run(kill_after_confirmation())
    _, publisher = seed_bundle(tools=True, overrides=overrides)
    with daemon_process(tmp_path, publishers=[publisher], label='resource-recovered') as recovered:
        async def inspect():
            client = await connect(recovered.data_dir, authority=actor)
            try:
                terminal, done = await client.wait_task(task.task_id, timeout_s=15)
                assert done and terminal['status'] == 'SUCCEEDED', terminal
                execution = await client.get_task_execution(task.task_id)
                assert [row['kind'] for row in execution['invocations']] == ['MODEL','CAPABILITY','MODEL']
                actual = execution['invocations'][1]
                assert actual['invocation_id'] == confirmed['invocation_id'] and actual['output_artifact_id'] == confirmed['output_artifact_id']
                assert execution['consumed_budget']['steps'] == 3
                current = await client.get_state(realm_id=REALM, actor_id=actor.actor_id, state_id=state['state_id'])
                result = json.loads(await client.get_artifact_content(actual['output_artifact_id']))
                assert current['cas_revision'] == 2 and current['state_revision_id'] == result['state_revision_id']
            finally:
                await client.aclose()
        asyncio.run(inspect())


def test_invalid_resource_normalizer_never_commits_state_write(tmp_path):
    original = files('agent_meta_seed_harness').joinpath('capabilities/state.py').read_bytes()
    override = original.replace(b'return InvocationResult(content=canonical_json(value))', b"return InvocationResult(content=b'[]')")
    assert override != original
    with tools_environment(tmp_path, overrides={'agent_meta_seed_harness/capabilities/state.py':override}) as (owner, actor, state, replacement):
        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                _, terminal, execution = await submit_tools(client, actor, [{'name':'seed.state.write','arguments':{
                    'state_id':state['state_id'],'expected_state_revision_id':state['state_revision_id'],'content_artifact_id':replacement}}])
                assert terminal['error'] == 'INVALID_RESULT' and len(execution['invocations']) == 2
                assert execution['invocations'][1]['output_artifact_id'] is None
                current = await client.get_state(realm_id=REALM, actor_id=actor.actor_id, state_id=state['state_id'])
                assert current['cas_revision'] == 1 and current['state_revision_id'] == state['state_revision_id']
            finally:
                await client.aclose()
        asyncio.run(run())


def test_individually_bounded_artifact_reads_cannot_overflow_the_terminal(tmp_path):
    with tools_environment(tmp_path) as (owner, actor, state, replacement):
        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                large = await upload(client, actor, {'blob':'x'*600000})
                _, terminal, execution = await submit_tools(client, actor, [
                    {'name':'seed.artifact.read','arguments':{'artifact_id':large}},
                    {'name':'seed.artifact.read','arguments':{'artifact_id':large}},
                ])
                assert terminal['status'] == 'FAILED' and terminal['error'] == 'RESOURCE_EXHAUSTED', terminal
                assert [row['kind'] for row in execution['invocations']] == ['MODEL','CAPABILITY','CAPABILITY','MODEL']
                for tool in execution['invocations'][1:3]:
                    assert tool['status'] == 'SUCCEEDED'
                    output = await client.get_artifact_content(tool['output_artifact_id'])
                    assert len(output) < 1024*1024 and json.loads(output)['content']['value'] == {'blob':'x'*600000}
                assert execution['invocations'][-1]['output_artifact_id'] is None
                assert execution['consumed_budget']['steps'] == 4
            finally:
                await client.aclose()
        asyncio.run(run())
