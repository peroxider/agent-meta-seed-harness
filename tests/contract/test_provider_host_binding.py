"""Independent public CLI/SDK -> signed Seed -> native synthetic Provider.

Loopback TEST mode only. No private Runtime import, key/DB/CAS read, live
gateway, captured R2, Managed isolation or release/support claim.
"""
import asyncio
import json
import os
import uuid

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.host import decode_model_response
from agent_meta_runtime.sdk.packages import canonical_json,sha256_hex
from provider_host_fixture import loopback_provider,provider_inputs,provider_bundle,provision,SECRET
from seed_actor import create_actor
from seed_package import activate_seed,wait_ready
from seed_runtime import admin,daemon_process


@pytest.mark.parametrize('mode',['text','tools','unknown_usage','disconnect','missing_binding','missing_credential','budget','rate','unpriceable'])
def test_seed_provider_uses_only_the_public_host_and_controlled_root_transport(tmp_path,mode):
    with loopback_provider(tmp_path,mode) as (server,ca):
        configuration,artifacts=provider_inputs(server.server_port,priced=(mode!='unpriceable'))
        bundle,publisher=provider_bundle(configuration,artifacts)
        manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        with daemon_process(tmp_path,publishers=[publisher],controlled_provider_test_ca=ca) as owner:
            data=owner.data_dir
            authority=create_actor(data,permissions=['artifact.put','task.submit','model.invoke','capability.invoke'])
            async def run():
                client=await connect(data,authority=authority)
                try:
                    for ref,raw in sorted(bundle.artifacts.items()):
                        uploaded=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,content=raw,
                            kind='code',media_type='application/octet-stream')
                        assert uploaded['artifact_id']==ref
                    validation=await client.validate_harness_package(bundle.manifest_artifact_id)
                    assert validation['valid'],validation
                    installed=await asyncio.to_thread(admin,data,'harness','install','--name',manifest['package_name'],'--version',manifest['package_version'],
                        bundle.manifest_artifact_id,bundle.package_artifact_id)
                    handle=('credential://'+('windows-dpapi/' if os.name=='nt' else 'insecure-dev/')+str(uuid.uuid4())
                        if mode=='missing_credential' else await asyncio.to_thread(provision,data))
                    if mode!='missing_binding':
                        approved=await asyncio.to_thread(admin,data,'harness','configure-provider',installed['harness_id'],
                            '--capability','capability://seed.messages-model','--profile-artifact',configuration['profile_artifact_id'],
                            '--credential-handle',handle)
                        assert approved['configuration_revision']==1
                    await asyncio.to_thread(activate_seed,data,bundle,installed['harness_id'])
                    await wait_ready(data)
                    input=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,
                        content=canonical_json({'provider':'messages','value':'synthetic independent Provider input'}),kind='task_input',media_type='application/json')
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,input_artifact_id=input['artifact_id'],
                        budget={'max_cost_microunits':0 if mode=='budget' else 100000})
                    terminal,done=await client.wait_task(task.task_id,timeout_s=30)
                    assert done
                    execution=await client.get_task_execution(task.task_id)
                    if mode in ('missing_binding','missing_credential','budget','unpriceable'):
                        assert terminal['error']=={'missing_binding':'FAILED_PRECONDITION','missing_credential':'KEY_UNAVAILABLE','budget':'RESOURCE_EXHAUSTED','unpriceable':'FAILED_PRECONDITION'}[mode],terminal
                        assert execution['invocations']==[] and server.requests==[]
                        return
                    expected=['MODEL','CAPABILITY','MODEL'] if mode=='tools' else ['MODEL']
                    assert [row['kind'] for row in execution['invocations']]==expected,(terminal,execution)
                    assert len(server.requests)==(2 if mode=='tools' else 1) and all(server.authorized)
                    view=json.loads(await client.get_artifact_content(execution['acceptance_view_artifact_id']))
                    current=(await client.get_harness(installed['harness_id']))['provider_configuration']
                    assert view['provider_configuration_fact_id']==current['configuration_fact_id']
                    if mode=='disconnect':
                        assert terminal['status']=='FAILED_RECOVERY' and terminal['error']=='EXTERNAL_EFFECT_UNKNOWN'
                        assert execution['consumed_budget']['cost_microunits'] is None
                    elif mode=='rate':
                        assert terminal['status']=='FAILED' and terminal['error']=='RESOURCE_EXHAUSTED'
                        observed=execution['invocations'][0]['provider']
                        assert observed['terminal']['http_status']==429 and observed['terminal']['retry_after_us']==2_000_000
                        assert observed['terminal']['error_code']=='RESOURCE_EXHAUSTED'
                        assert observed['settlement']['usage']['cost_microunits'] is None
                        assert observed['settlement']['liability_microunits']==observed['reservation']['maximum_cost_microunits']>0
                        assert len(server.requests)==1
                    else:
                        assert terminal['status']=='SUCCEEDED',terminal
                        models=[row for row in execution['invocations'] if row['kind']=='MODEL']
                        costs=[]
                        for row,request in zip(models,server.requests):
                            response=decode_model_response(await client.get_artifact_content(row['output_artifact_id']))
                            tokens=len(canonical_json({key:request[key] for key in ('messages','system','tools','tool_choice') if key in request}))
                            assert response.usage.input_tokens==(None if mode=='unknown_usage' else tokens)
                            assert response.usage.cost_microunits==(None if mode=='unknown_usage' else tokens+2)
                            costs.append(response.usage.cost_microunits)
                        assert execution['consumed_budget']['cost_microunits']==(None if mode=='unknown_usage' else sum(costs))
                        if mode=='tools':
                            result=server.requests[1]['messages'][-1]['content'][0]
                            assert result['type']=='tool_result' and result['tool_use_id']=='typed-call-1'
                            assert json.loads(result['content'])=={'value':'typed'}
                    trace=await client.get_task_trace(task.task_id)
                    assert SECRET not in canonical_json({'terminal':terminal,'execution':execution,'trace':trace,'configuration':current})
                finally:
                    await client.aclose()
            asyncio.run(run())


def test_provider_credential_never_leaves_the_handle_boundary(tmp_path):
    with loopback_provider(tmp_path,'tools') as (server,ca):
        configuration,artifacts=provider_inputs(server.server_port)
        bundle,publisher=provider_bundle(configuration,artifacts)
        manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        with daemon_process(tmp_path,publishers=[publisher],controlled_provider_test_ca=ca) as owner:
            data=owner.data_dir
            authority=create_actor(data,permissions=['artifact.put','task.submit','model.invoke','capability.invoke'])
            async def run():
                client=await connect(data,authority=authority)
                try:
                    for ref,raw in sorted(bundle.artifacts.items()):
                        assert (await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,content=raw,
                            kind='code',media_type='application/octet-stream'))['artifact_id']==ref
                    installed=await asyncio.to_thread(admin,data,'harness','install','--name',manifest['package_name'],
                        '--version',manifest['package_version'],bundle.manifest_artifact_id,bundle.package_artifact_id)
                    handle=await asyncio.to_thread(provision,data)
                    await asyncio.to_thread(admin,data,'harness','configure-provider',installed['harness_id'],
                        '--capability','capability://seed.messages-model','--profile-artifact',configuration['profile_artifact_id'],
                        '--credential-handle',handle)
                    await asyncio.to_thread(activate_seed,data,bundle,installed['harness_id'])
                    await wait_ready(data)
                    uploaded=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,
                        content=canonical_json({'provider':'messages','value':'containment boundary'}),kind='task_input',media_type='application/json')
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                        input_artifact_id=uploaded['artifact_id'],budget={'max_cost_microunits':100000})
                    terminal,done=await client.wait_task(task.task_id,timeout_s=30)
                    assert terminal['status']=='SUCCEEDED',terminal
                    execution=await client.get_task_execution(task.task_id)
                    # A real model+tool run must have happened, otherwise the
                    # scan below proves nothing.
                    assert [row['kind'] for row in execution['invocations']]==['MODEL','CAPABILITY','MODEL']
                    assert len(server.requests)==2 and all(server.authorized)
                    trace=await client.get_task_trace(task.task_id)
                    harness=await client.get_harness(installed['harness_id'])
                    view=json.loads(await client.get_artifact_content(execution['acceptance_view_artifact_id']))
                    doctor=await asyncio.to_thread(admin,data,'doctor')
                    grants=json.loads(bundle.artifacts[manifest['grant_requests_artifact_id']])
                    def text_or_hash(raw):
                        try:
                            return raw.decode('utf-8')
                        except UnicodeDecodeError:
                            return {'sha256':sha256_hex(raw)}
                    model_outputs=[]
                    for row in execution['invocations']:
                        if row['output_artifact_id'] is not None:
                            model_outputs.append(await client.get_artifact_content(row['output_artifact_id']))
                    surfaces={'terminal':terminal,'trace':trace,'harness':harness,'view':view,'doctor':doctor,
                        'manifest':manifest,'grants':grants,'provider_artifacts':{ref:text_or_hash(raw) for ref,raw in bundle.artifacts.items()},
                        'outputs':model_outputs,'stdout':owner.output.read_text(errors='replace'),
                        'stderr':owner.errors.read_text(errors='replace')}
                    blob=json.dumps(surfaces,sort_keys=True,default=lambda value:value.hex() if isinstance(value,(bytes,bytearray)) else str(value)).encode()
                    blob+=canonical_json({'terminal':terminal,'execution':execution,'trace':trace,'harness':harness,
                        'view':view,'doctor':doctor,'manifest':manifest,'grants':grants})
                    assert SECRET not in blob
                    assert sha256_hex(SECRET).encode() not in blob
                    assert doctor['ok'] is True and doctor['findings']==[],doctor
                    reported=harness['provider_configuration']['credential_handle']
                    assert reported.startswith('credential://') and reported==handle
                    assert reported.encode() in blob
                finally:
                    await client.aclose()
            asyncio.run(run())
