"""SH-PROV-03 live Provider job: fail-closed authorization scaffolding.

The real controlled live call is a separate operator-gated job. This named
module owns the plan's explicit-enablement, hard count/cost/timeout and
no-pseudo-success gates. ``docs/provider-usage-authorization.json`` is
operator-local and never committed; the committed example defaults to no
live permission. These tests never send a live request and never read the
operator-local authorization file. The full offline suite ignores this file
by plan; the explicit live job command runs it.
"""
import asyncio
import json
import os
from pathlib import Path
import uuid

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json
from provider_host_fixture import loopback_provider,provider_inputs,provider_bundle
from seed_actor import create_actor
from seed_package import activate_seed,wait_ready
from seed_runtime import admin,daemon_process


EXAMPLE=Path(__file__).resolve().parents[2]/'docs/provider-usage-authorization.example.json'


class LiveRefusal(Exception):
    def __init__(self,code):
        super().__init__(code)
        self.code=code


def load_authorization(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise LiveRefusal('AUTHORIZATION_MISSING')
    if not isinstance(value,dict):
        raise LiveRefusal('AUTHORIZATION_INVALID')
    return value


def live_plan(authorization):
    """Every gate refuses before any wire byte; nothing defaults to allow."""
    if authorization.get('schema')!='seed-provider-usage-authorization/v1':
        raise LiveRefusal('AUTHORIZATION_INVALID')
    if authorization.get('live_requests_authorized') is not True:
        raise LiveRefusal('NOT_AUTHORIZED')
    if authorization.get('paid_fallback_allowed') is not False:
        raise LiveRefusal('PAID_FALLBACK_FORBIDDEN')
    if authorization.get('stop_on_rate_limit') is not True:
        raise LiveRefusal('RATE_LIMIT_STOP_REQUIRED')
    ceiling=authorization.get('incremental_cost_ceiling_micros')
    if not isinstance(ceiling,int) or isinstance(ceiling,bool) or ceiling<0:
        raise LiveRefusal('COST_UNBOUNDED')
    maximum_requests=authorization.get('live_request_budget')
    if not isinstance(maximum_requests,int) or isinstance(maximum_requests,bool) or maximum_requests<1:
        raise LiveRefusal('COUNT_UNBOUNDED')
    timeout_s=authorization.get('request_timeout_s')
    if not isinstance(timeout_s,(int,float)) or isinstance(timeout_s,bool) or not timeout_s>0:
        raise LiveRefusal('TIMEOUT_UNBOUNDED')
    handle=authorization.get('credential_handle')
    if not isinstance(handle,str) or not handle.startswith('credential://'):
        raise LiveRefusal('CREDENTIAL_MISSING')
    return {'maximum_requests':maximum_requests,'cost_ceiling_micros':ceiling,
        'request_timeout_s':timeout_s,'credential_handle':handle}


def test_committed_example_defaults_refuse_live_execution():
    authorization=load_authorization(EXAMPLE)
    assert authorization['live_requests_authorized'] is False
    assert authorization['live_requests_performed']==0
    assert authorization['paid_fallback_allowed'] is False
    assert authorization['stop_on_rate_limit'] is True
    assert authorization['incremental_cost_ceiling_micros']==0
    with pytest.raises(LiveRefusal) as caught:
        live_plan(authorization)
    assert caught.value.code=='NOT_AUTHORIZED'


def test_missing_authorization_file_refuses_before_any_wire_activity(tmp_path):
    with pytest.raises(LiveRefusal) as caught:
        load_authorization(tmp_path/'provider-usage-authorization.json')
    assert caught.value.code=='AUTHORIZATION_MISSING'


@pytest.mark.parametrize('field,value,code', [
    ('schema','wrong/v1','AUTHORIZATION_INVALID'),
    ('live_requests_authorized',False,'NOT_AUTHORIZED'),
    ('paid_fallback_allowed',True,'PAID_FALLBACK_FORBIDDEN'),
    ('stop_on_rate_limit',False,'RATE_LIMIT_STOP_REQUIRED'),
    ('incremental_cost_ceiling_micros',None,'COST_UNBOUNDED'),
    ('incremental_cost_ceiling_micros',-1,'COST_UNBOUNDED'),
    ('live_request_budget',None,'COUNT_UNBOUNDED'),
    ('live_request_budget',0,'COUNT_UNBOUNDED'),
    ('request_timeout_s',None,'TIMEOUT_UNBOUNDED'),
    ('request_timeout_s',0,'TIMEOUT_UNBOUNDED'),
    ('credential_handle','sk-plaintext-secret','CREDENTIAL_MISSING'),
    ('credential_handle',None,'CREDENTIAL_MISSING')])
def test_enabled_authorization_still_requires_every_hard_limit(field,value,code):
    authorization={'schema':'seed-provider-usage-authorization/v1','live_requests_authorized':True,
        'paid_fallback_allowed':False,'stop_on_rate_limit':True,
        'incremental_cost_ceiling_micros':0,'live_request_budget':1,'request_timeout_s':30,
        'credential_handle':'credential://operator-store/example'}
    if value is None:
        authorization.pop(field)
    else:
        authorization[field]=value
    with pytest.raises(LiveRefusal) as caught:
        live_plan(authorization)
    assert caught.value.code==code
    plan=live_plan({'schema':'seed-provider-usage-authorization/v1','live_requests_authorized':True,
        'paid_fallback_allowed':False,'stop_on_rate_limit':True,
        'incremental_cost_ceiling_micros':0,'live_request_budget':1,'request_timeout_s':30,
        'credential_handle':'credential://operator-store/example'})
    assert plan=={'maximum_requests':1,'cost_ceiling_micros':0,'request_timeout_s':30,
        'credential_handle':'credential://operator-store/example'}


def test_missing_credential_refuses_explicitly_with_zero_invocations_and_wire_bytes(tmp_path):
    with loopback_provider(tmp_path,'text') as (server,ca):
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
                    # No configure-provider call at all: the binding gate refuses.
                    await asyncio.to_thread(activate_seed,data,bundle,installed['harness_id'])
                    await wait_ready(data)
                    uploaded=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,
                        content=canonical_json({'provider':'messages','value':'live precondition'}),kind='task_input',media_type='application/json')
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                        input_artifact_id=uploaded['artifact_id'],budget={'max_cost_microunits':100000})
                    terminal,done=await client.wait_task(task.task_id,timeout_s=30)
                    assert done and terminal['status']=='FAILED' and terminal['error']=='FAILED_PRECONDITION',terminal
                    execution=await client.get_task_execution(task.task_id)
                    assert execution['invocations']==[]
                    # An approved-but-unresolvable handle refuses just as
                    # explicitly; neither case reports success.
                    await asyncio.to_thread(admin,data,'harness','configure-provider',installed['harness_id'],
                        '--capability','capability://seed.messages-model','--profile-artifact',configuration['profile_artifact_id'],
                        '--credential-handle','credential://'+('windows-dpapi/' if os.name=='nt' else 'insecure-dev/')+str(uuid.uuid4()))
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                        input_artifact_id=uploaded['artifact_id'],budget={'max_cost_microunits':100000})
                    terminal,done=await client.wait_task(task.task_id,timeout_s=30)
                    assert done and terminal['status']=='FAILED' and terminal['error']=='KEY_UNAVAILABLE',terminal
                    execution=await client.get_task_execution(task.task_id)
                    assert execution['invocations']==[]
                    assert server.requests==[]
                finally:
                    await client.aclose()
            asyncio.run(run())
