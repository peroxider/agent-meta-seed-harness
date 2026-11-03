"""Independent child Action evidence via native public daemons and owned logs."""
import asyncio
from importlib.resources import files
import json

import pytest

from agent_meta_runtime.sdk import connect
from recovery_runtime import probe_events
from seed_package import seed_bundle
from seed_runtime import daemon_process
from toolset_runtime import REALM, tools_environment, submit_tools, upload


@pytest.mark.parametrize('backend', ['trusted_in_process','in_memory'])
def test_ordinary_tools_have_distinct_children_and_complete_output_provenance(tmp_path, backend):
    with tools_environment(tmp_path, execution_backend=backend) as (owner, actor, state, replacement):
        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                task, terminal, execution = await submit_tools(client, actor, [
                    {'name':'seed.transform.normalize_json','arguments':{'json':'{"answer":42}'}},
                    {'name':'seed.echo','arguments':{'value':'typed ordinary tool'}},
                ])
                assert terminal['status'] == 'SUCCEEDED', terminal
                trace = await client.get_task_trace(task.task_id)
                tools = execution['invocations'][1:-1]
                assert len(tools) == 2 and len({row['action_id'] for row in tools}) == 2
                assert len(trace['actions']) == 3
                for tool in tools:
                    child = next(row for row in trace['actions'] if row['action_id']==tool['action_id'])
                    assert child['intent']=='capability_tool' and child['status']=='SUCCEEDED'
                    assert child['causal_parent_action_id']==execution['root_action_id']
                    assert child['consumed_budget']['steps']==1 and child['consumed_budget']['effects']==0
                    for edge_type, source, target in (
                            ('caused_by',child['action_id'],execution['root_action_id']),
                            ('part_of',tool['invocation_id'],child['action_id']),
                            ('used',child['action_id'],tool['input_artifact_id']),
                            ('produced',tool['invocation_id'],tool['output_artifact_id'])):
                        assert any(e['edge_type']==edge_type and e['from_id']==source and e['to_id']==target for e in trace['edges'])
                    assert len([e for e in trace['edges'] if e['edge_type']=='authorized_by' and e['from_id']==child['action_id']])==2
                    if backend=='in_memory':
                        assert tool['execution_binding']['backend_id']=='backend://inmemory'
                        assert any(e['event_type']=='execution_submitted' and e['action_id']==child['action_id'] for e in trace['events'])
                    else:
                        assert tool.get('execution_binding') is None
            finally:
                await client.aclose()
        asyncio.run(run())


@pytest.mark.parametrize('backend', ['trusted_in_process','in_memory'])
def test_confirmed_ordinary_child_and_callback_are_not_recreated_after_process_kill(tmp_path, backend):
    loop = files('agent_meta_seed_harness').joinpath('loop.py').read_bytes()
    transform = files('agent_meta_seed_harness').joinpath('capabilities/transform.py').read_bytes()
    loop = b'import asyncio\n' + loop.replace(b'result = await host.invoke_tool(call)',
        b'result = await host.invoke_tool(call)\n            await asyncio.sleep(1)')
    transform = transform.replace(b'async def normalize_json(request):', b'async def normalize_json(request):\n'
        b'    print(json.dumps({"seed_probe_call":"transform","task_id":request.task.task_id}), flush=True)')
    overrides = {'agent_meta_seed_harness/loop.py':loop,'agent_meta_seed_harness/capabilities/transform.py':transform}
    with tools_environment(tmp_path, overrides=overrides, execution_backend=backend) as (owner, actor, state, replacement):
        async def kill():
            client = await connect(owner.data_dir, authority=actor)
            try:
                reference = await upload(client, actor, {'provider':'fake-tools','calls':[
                    {'name':'seed.transform.normalize_json','arguments':{'json':'{"answer":42}'}}]}, 'task_input')
                task = await client.submit_task(realm_id=REALM,actor_id=actor.actor_id,input_artifact_id=reference)
                end = asyncio.get_running_loop().time()+10
                while asyncio.get_running_loop().time()<end:
                    execution = await client.get_task_execution(task.task_id)
                    confirmed = [row for row in execution['invocations'] if row['kind']=='CAPABILITY' and row['status']=='SUCCEEDED']
                    if confirmed:
                        assert len(execution['invocations'])==2
                        assert len([e for e in probe_events(owner) if e.get('seed_probe_call')=='transform' and e.get('task_id')==task.task_id])==1
                        owner.process.kill()
                        owner.process.wait(timeout=10)
                        return task, confirmed[0]
                    await asyncio.sleep(.01)
                raise AssertionError('ordinary tool confirmation deadline exceeded')
            finally:
                await client.aclose()
        task, confirmed = asyncio.run(kill())
    _, publisher = seed_bundle(tools=True,overrides=overrides)
    with daemon_process(tmp_path,publishers=[publisher],execution_backend=backend,label='ordinary-recovered') as recovered:
        async def inspect():
            client = await connect(recovered.data_dir,authority=actor)
            try:
                terminal, done = await client.wait_task(task.task_id,timeout_s=15)
                assert done and terminal['status']=='SUCCEEDED',terminal
                execution = await client.get_task_execution(task.task_id)
                assert [row['kind'] for row in execution['invocations']]==['MODEL','CAPABILITY','MODEL']
                actual = execution['invocations'][1]
                assert actual['invocation_id']==confirmed['invocation_id'] and actual['action_id']==confirmed['action_id']
                assert actual['output_artifact_id']==confirmed['output_artifact_id']
                assert execution['consumed_budget']['steps']==3
                assert not [e for e in probe_events(recovered) if e.get('seed_probe_call')=='transform']
                trace = await client.get_task_trace(task.task_id)
                assert len(trace['actions'])==2
                child = next(row for row in trace['actions'] if row['action_id']==actual['action_id'])
                assert child['intent']=='capability_tool' and child['status']=='SUCCEEDED'
            finally:
                await client.aclose()
        asyncio.run(inspect())
