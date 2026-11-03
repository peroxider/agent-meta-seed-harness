"""Crash real public daemons around actual synthetic Provider responses.

Only public SDK/CLI plus owned-process and loopback-server observations are
used. No Runtime implementation import, database, CAS or key file is read.
"""
import asyncio
import json
import time

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json
from provider_host_fixture import loopback_provider,provider_inputs,provider_bundle,provision,SECRET
from recovery_runtime import wait_invocations
from seed_actor import create_actor
from seed_package import activate_seed,wait_ready
from seed_runtime import admin,daemon_process


PRECOMMIT_BINDING=b'''
import json
import time
from agent_meta_runtime.sdk.host import HarnessAdapter,HealthStatus,ProviderAdapter
from .capabilities.echo import echo
from .loop import run_task
from .provider_config import CONFIGURATION
from .providers.messages import MessagesProvider

async def probe(request):
    return HealthStatus('READY','SYNTHETIC_RECOVERY_PROBE')

def create():
    provider=MessagesProvider(**CONFIGURATION)
    def normalize(terminal):
        value=provider.normalize(terminal)
        if json.loads(terminal.content)['id']=='msg_precommit':
            print('{"seed_provider_precommit":true}',flush=True)
            time.sleep(60)
        return value
    return HarnessAdapter(run_task,None,{'seed.echo':echo},probe,provider=ProviderAdapter(provider.prepare,normalize))
'''


@pytest.mark.parametrize('boundary',['accepted','response_before_commit'])
def test_provider_crash_remains_unknown_after_restart_without_resend(tmp_path,boundary):
    mode='hold_for_owner_death' if boundary=='accepted' else 'pause_before_commit'
    with loopback_provider(tmp_path,mode) as (server,ca):
        configuration,artifacts=provider_inputs(server.server_port)
        overrides={'agent_meta_seed_harness/host_binding_provider.py':PRECOMMIT_BINDING} if boundary=='response_before_commit' else None
        bundle,publisher=provider_bundle(configuration,artifacts,overrides=overrides)
        manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        with daemon_process(tmp_path,publishers=[publisher],label='original',controlled_provider_test_ca=ca) as original:
            data=original.data_dir
            authority=create_actor(data,permissions=['artifact.put','task.submit','model.invoke','capability.invoke'])
            async def submit_then_crash():
                client=await connect(data,authority=authority)
                try:
                    for ref,raw in sorted(bundle.artifacts.items()):
                        assert (await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,content=raw,
                            kind='code',media_type='application/octet-stream'))['artifact_id']==ref
                    report=await client.validate_harness_package(bundle.manifest_artifact_id)
                    assert report['valid'],report
                    installed=await asyncio.to_thread(admin,data,'harness','install','--name',manifest['package_name'],
                        '--version',manifest['package_version'],bundle.manifest_artifact_id,bundle.package_artifact_id)
                    handle=await asyncio.to_thread(provision,data)
                    await asyncio.to_thread(admin,data,'harness','configure-provider',installed['harness_id'],
                        '--capability','capability://seed.messages-model','--profile-artifact',configuration['profile_artifact_id'],
                        '--credential-handle',handle)
                    await asyncio.to_thread(activate_seed,data,bundle,installed['harness_id']); await wait_ready(data)
                    uploaded=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,
                        content=canonical_json({'provider':'messages','value':'synthetic crash boundary'}),kind='task_input',media_type='application/json')
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,input_artifact_id=uploaded['artifact_id'],
                        budget={'max_cost_microunits':100000})
                    async with asyncio.timeout(8):
                        while not server.received.is_set():
                            await asyncio.sleep(.005)
                        if boundary=='response_before_commit':
                            while '"seed_provider_precommit":true' not in original.output.read_text():
                                assert original.process.poll() is None
                                await asyncio.sleep(.005)
                        else:
                            await wait_invocations(data,task.task_id,statuses=['RUNNING'])
                    # This is earlier than the fixture's ten-second deadline.
                    # Peer closure must be caused by ownership loss, not timeout.
                    assert time.monotonic()-server.received_at<3
                    original.process.kill(); await asyncio.to_thread(original.process.wait,10)
                    if boundary=='accepted':
                        assert await asyncio.to_thread(server.peer_closed.wait,2), 'native Provider connection survived owner loss'
                    assert len(server.requests)==1 and all(server.authorized)
                    return task,uploaded['artifact_id']
                finally:
                    await client.aclose()
            task,input_ref=asyncio.run(submit_then_crash())
            server.mode='text'
            with daemon_process(tmp_path,publishers=[publisher],label='restarted',controlled_provider_test_ca=ca):
                async def recover():
                    client=await connect(data,authority=authority)
                    try:
                        result,done=await client.wait_task(task.task_id,timeout_s=10)
                        assert done and result['status']=='FAILED_RECOVERY' and result['error']=='EXTERNAL_EFFECT_UNKNOWN',result
                        execution=await client.get_task_execution(task.task_id)
                        assert len(execution['invocations'])==1 and execution['invocations'][0]['status']=='FAILED'
                        assert execution['consumed_budget']['model_calls']==execution['consumed_budget']['effects']==1
                        assert execution['consumed_budget']['cost_microunits'] is None
                        accounting=execution['invocations'][0]['provider']
                        assert accounting['terminal'] is None and accounting['settlement']['outcome']=='UNKNOWN'
                        assert accounting['settlement']['liability_microunits']==accounting['reservation']['maximum_cost_microunits']>0
                        old_id=execution['invocations'][0]['invocation_id']
                        await wait_ready(data)
                        again=await client.get_task_execution(task.task_id)
                        assert again['invocations'][0]['invocation_id']==old_id and len(server.requests)==1
                        fresh=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,input_artifact_id=input_ref,
                            budget={'max_cost_microunits':100000})
                        terminal,done=await client.wait_task(fresh.task_id,timeout_s=10)
                        assert done and terminal['status']=='SUCCEEDED',terminal
                        assert len(server.requests)==2 and all(server.authorized)
                        assert SECRET not in canonical_json({'old':execution,'fresh':terminal})
                    finally:
                        await client.aclose()
                asyncio.run(recover())
