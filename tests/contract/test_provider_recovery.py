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


async def prepare_provider(data,authority,bundle,manifest,configuration):
    client=await connect(data,authority=authority)
    try:
        for ref,raw in sorted(bundle.artifacts.items()):
            assert (await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,content=raw,
                kind='code',media_type='application/octet-stream'))['artifact_id']==ref
        report=await client.validate_harness_package(bundle.manifest_artifact_id)
        assert report['valid'],report
    finally:
        await client.aclose()
    installed=await asyncio.to_thread(admin,data,'harness','install','--name',manifest['package_name'],
        '--version',manifest['package_version'],bundle.manifest_artifact_id,bundle.package_artifact_id)
    handle=await asyncio.to_thread(provision,data)
    await asyncio.to_thread(admin,data,'harness','configure-provider',installed['harness_id'],
        '--capability','capability://seed.messages-model','--profile-artifact',configuration['profile_artifact_id'],
        '--credential-handle',handle)
    await asyncio.to_thread(activate_seed,data,bundle,installed['harness_id'])
    await wait_ready(data)


def test_provider_presend_failure_is_known_never_unknown_and_never_resent(tmp_path):
    with loopback_provider(tmp_path,'text') as (server,ca):
        configuration,artifacts=provider_inputs(server.server_port)
        bundle,publisher=provider_bundle(configuration,artifacts)
        manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        # The profile now points at a port with no listener: the request can
        # never be sent, so the boundary is observable with zero wire bytes.
        server.shutdown(); server.server_close()
        with daemon_process(tmp_path,publishers=[publisher],label='presend',controlled_provider_test_ca=ca) as owner:
            data=owner.data_dir
            authority=create_actor(data,permissions=['artifact.put','task.submit','model.invoke','capability.invoke'])
            async def run():
                client=await connect(data,authority=authority)
                try:
                    await prepare_provider(data,authority,bundle,manifest,configuration)
                    uploaded=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,
                        content=canonical_json({'provider':'messages','value':'presend boundary'}),kind='task_input',media_type='application/json')
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                        input_artifact_id=uploaded['artifact_id'],budget={'max_cost_microunits':100000})
                    result,done=await client.wait_task(task.task_id,timeout_s=30)
                    assert done and result['status']=='FAILED' and result['error']=='BACKEND_UNAVAILABLE',result
                    execution=await client.get_task_execution(task.task_id)
                    assert len(execution['invocations'])==1 and execution['invocations'][0]['status']=='FAILED'
                    assert execution['invocations'][0]['error']=='BACKEND_UNAVAILABLE'
                    assert execution['invocations'][0]['output_artifact_id'] is None
                    accounting=execution['invocations'][0]['provider']
                    assert accounting['settlement']['outcome']=='NOT_SENT'
                    assert accounting['settlement']['liability_microunits']==0
                    assert accounting['settlement']['usage']['cost_microunits']==0
                    assert accounting['reservation']['maximum_cost_microunits']>0
                    return uploaded['artifact_id'],execution['invocations'][0]['invocation_id'],task.task_id
                finally:
                    await client.aclose()
            input_ref,invocation_id,task_id=asyncio.run(run())
        with daemon_process(tmp_path,publishers=[publisher],label='presend-restart',controlled_provider_test_ca=ca):
            async def recover():
                client=await connect(data,authority=authority)
                try:
                    again=await client.get_task_execution(task_id)
                    assert again['invocations'][0]['invocation_id']==invocation_id
                    assert again['invocations'][0]['provider']['settlement']['outcome']=='NOT_SENT'
                    # A fresh Task fails identically: nothing is resent and
                    # no new attempt is minted for the unsent request.
                    fresh=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                        input_artifact_id=input_ref,budget={'max_cost_microunits':100000})
                    result,done=await client.wait_task(fresh.task_id,timeout_s=30)
                    assert done and result['status']=='FAILED' and result['error']=='BACKEND_UNAVAILABLE',result
                    fresh_execution=await client.get_task_execution(fresh.task_id)
                    assert len(fresh_execution['invocations'])==1
                    assert fresh_execution['invocations'][0]['provider']['settlement']['outcome']=='NOT_SENT'
                finally:
                    await client.aclose()
            asyncio.run(recover())


def test_provider_deadline_marks_unknown_and_a_late_response_cannot_reverse_it(tmp_path):
    with loopback_provider(tmp_path,'hold') as (server,ca):
        configuration,artifacts=provider_inputs(server.server_port)
        bundle,publisher=provider_bundle(configuration,artifacts)
        manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        with daemon_process(tmp_path,publishers=[publisher],label='deadline',controlled_provider_test_ca=ca) as owner:
            data=owner.data_dir
            authority=create_actor(data,permissions=['artifact.put','task.submit','model.invoke','capability.invoke'])
            async def run():
                client=await connect(data,authority=authority)
                try:
                    await prepare_provider(data,authority,bundle,manifest,configuration)
                    uploaded=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,
                        content=canonical_json({'provider':'messages','value':'deadline boundary'}),kind='task_input',media_type='application/json')
                    # The Task deadline fires before the fixture's held response.
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                        input_artifact_id=uploaded['artifact_id'],deadline_at_us=time.time_ns()//1000+2_000_000,
                        budget={'max_cost_microunits':100000})
                    async with asyncio.timeout(8):
                        while not server.received.is_set():
                            await asyncio.sleep(.005)
                    result,done=await client.wait_task(task.task_id,timeout_s=20)
                    # Both fail-closed Task labels are legitimate when the
                    # deadline fires while the wire request is in flight:
                    # TIMED_OUT when the owned worker exit is confirmed,
                    # FAILED_RECOVERY when cancellation cannot confirm it.
                    # The invocation accounting below is identical in both.
                    assert done and (result['status'],result['error']) in (
                        ('TIMED_OUT','DEADLINE_EXCEEDED'),('FAILED_RECOVERY','EXTERNAL_EFFECT_UNKNOWN')),result
                    execution=await client.get_task_execution(task.task_id)
                    assert execution['status']==result['status'] and execution['error']==result['error']
                    assert len(execution['invocations'])==1 and execution['invocations'][0]['status']=='FAILED'
                    assert execution['invocations'][0]['error']=='EXTERNAL_EFFECT_UNKNOWN'
                    accounting=execution['invocations'][0]['provider']
                    assert accounting['terminal']['state']=='UNKNOWN'
                    assert accounting['terminal']['error_code']=='EXTERNAL_EFFECT_UNKNOWN'
                    assert accounting['settlement']['outcome']=='UNKNOWN'
                    assert accounting['settlement']['usage']['cost_microunits'] is None
                    assert accounting['settlement']['liability_microunits']==accounting['reservation']['maximum_cost_microunits']>0
                    assert execution['consumed_budget']['model_calls']==1
                    assert execution['consumed_budget']['cost_microunits'] is None
                    assert len(server.requests)==1 and all(server.authorized)
                    # The provider answers late; the settled UNKNOWN outcome,
                    # the invocation identity and the terminal cannot change.
                    server.release.set()
                    await asyncio.sleep(2)
                    again=await client.get_task_execution(task.task_id)
                    assert again['invocations'][0]['invocation_id']==execution['invocations'][0]['invocation_id']
                    assert again['invocations'][0]['provider']['settlement']==accounting['settlement']
                    replayed,terminal=await client.wait_task(task.task_id,timeout_s=5)
                    assert terminal and replayed==result
                    assert len(server.requests)==1
                    return task.task_id,execution['invocations'][0]['invocation_id'],dict(accounting['settlement'])
                finally:
                    await client.aclose()
            task_id,invocation_id,settlement=asyncio.run(run())
        owner.process.kill(); owner.process.wait(timeout=10)
        with daemon_process(tmp_path,publishers=[publisher],label='deadline-restart',controlled_provider_test_ca=ca):
            async def recover():
                client=await connect(data,authority=authority)
                try:
                    again=await client.get_task_execution(task_id)
                    assert again['invocations'][0]['invocation_id']==invocation_id
                    assert again['invocations'][0]['provider']['settlement']==settlement
                    assert len(server.requests)==1
                finally:
                    await client.aclose()
            asyncio.run(recover())


def test_cancel_during_inflight_request_settles_unknown_and_replays_after_restart(tmp_path):
    with loopback_provider(tmp_path,'hold') as (server,ca):
        configuration,artifacts=provider_inputs(server.server_port)
        bundle,publisher=provider_bundle(configuration,artifacts)
        manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        with daemon_process(tmp_path,publishers=[publisher],label='cancel-inflight',controlled_provider_test_ca=ca) as owner:
            data=owner.data_dir
            authority=create_actor(data,permissions=['artifact.put','task.submit','task.cancel','model.invoke','capability.invoke'])
            async def run():
                client=await connect(data,authority=authority)
                try:
                    await prepare_provider(data,authority,bundle,manifest,configuration)
                    uploaded=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,
                        content=canonical_json({'provider':'messages','value':'cancel boundary'}),kind='task_input',media_type='application/json')
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                        input_artifact_id=uploaded['artifact_id'],budget={'max_cost_microunits':100000})
                    async with asyncio.timeout(8):
                        while not server.received.is_set():
                            await asyncio.sleep(.005)
                    # The wire request is in flight; the explicit cancel
                    # arrives now. The Task ends CANCELLED while the already
                    # sent external effect settles UNKNOWN with full liability.
                    cancel=client.build_envelope_jcs(realm_id='realm://main',actor_id=authority.actor_id,
                        payload_type='task.cancel/v1',payload={'task_id':task.task_id,'reason_code':'requested'},
                        command_id='task://019a44d0-0000-7000-8000-0000000000c1')
                    cancellation=await client.execute_command('agent_meta.public.v1.Task.Cancel',cancel)
                    result,done=await client.wait_task(task.task_id,timeout_s=15)
                    assert done and result['status']=='CANCELLED',result
                    execution=await client.get_task_execution(task.task_id)
                    assert len(execution['invocations'])==1 and execution['invocations'][0]['status']=='FAILED'
                    assert execution['invocations'][0]['error']=='EXTERNAL_EFFECT_UNKNOWN'
                    accounting=execution['invocations'][0]['provider']
                    assert accounting['terminal']['state']=='UNKNOWN'
                    assert accounting['terminal']['error_code']=='EXTERNAL_EFFECT_UNKNOWN'
                    assert accounting['settlement']['outcome']=='UNKNOWN'
                    assert accounting['settlement']['usage']['cost_microunits'] is None
                    assert accounting['settlement']['liability_microunits']==accounting['reservation']['maximum_cost_microunits']>0
                    assert execution['consumed_budget']['model_calls']==1
                    assert execution['consumed_budget']['cost_microunits'] is None
                    assert len(server.requests)==1 and all(server.authorized)
                    # The provider answers late; the cancelled outcome, the
                    # invocation identity and its settlement cannot change.
                    server.release.set()
                    await asyncio.sleep(2)
                    again=await client.get_task_execution(task.task_id)
                    assert again['invocations'][0]['invocation_id']==execution['invocations'][0]['invocation_id']
                    assert again['invocations'][0]['provider']['settlement']==accounting['settlement']
                    replayed,terminal=await client.wait_task(task.task_id,timeout_s=5)
                    assert terminal and replayed==result
                    assert len(server.requests)==1
                    return task.task_id,execution['invocations'][0]['invocation_id'],dict(accounting['settlement']),cancel,cancellation
                finally:
                    await client.aclose()
            task_id,invocation_id,settlement,cancel,cancellation=asyncio.run(run())
        owner.process.kill(); owner.process.wait(timeout=10)
        with daemon_process(tmp_path,publishers=[publisher],label='cancel-restart',controlled_provider_test_ca=ca):
            async def recover():
                client=await connect(data,authority=authority)
                try:
                    again=await client.get_task_execution(task_id)
                    assert again['invocations'][0]['invocation_id']==invocation_id
                    assert again['invocations'][0]['provider']['settlement']==settlement
                    assert await client.execute_command('agent_meta.public.v1.Task.Cancel',cancel)==cancellation
                    replayed,terminal=await client.wait_task(task_id,timeout_s=5)
                    assert terminal and replayed['status']=='CANCELLED'
                    assert len(server.requests)==1
                finally:
                    await client.aclose()
            asyncio.run(recover())
