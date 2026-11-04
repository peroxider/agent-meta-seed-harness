"""Retry-policy boundary: only the packaging gate and an explicit new Task.

The selected profile fixes ``UNAVAILABLE_NO_RETRY``: no durable upstream
lookup exists, so no code path may treat a not-accepted request as retryable.
These proofs pin (1) that a profile declaring any other lookup policy cannot
even be built into a package, and (2) that after a pre-send failure the
endpoint's return helps only an explicitly submitted new Task — the original
request stays settled ``NOT_SENT`` and is never resent.
"""
import asyncio
import json
import ssl
import threading

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from provider_host_fixture import Handler, Server, loopback_provider, provider_bundle, provider_inputs, provision
from seed_actor import create_actor
from seed_package import activate_seed, wait_ready
from seed_runtime import admin, daemon_process


def test_provider_profile_lookup_policy_is_fail_closed_at_packaging():
    configuration, artifacts = provider_inputs(8443)
    profile_ref = configuration['profile_artifact_id']
    body = json.loads(artifacts[profile_ref])
    assert body['lookup_policy'] == 'UNAVAILABLE_NO_RETRY'
    body['lookup_policy'] = 'RETRY_WITH_LOOKUP'
    raw = canonical_json(body)
    del artifacts[profile_ref]
    configuration['profile_artifact_id'] = 'artifact://sha256/' + sha256_hex(raw)
    artifacts[configuration['profile_artifact_id']] = raw
    with pytest.raises(ValueError, match='explicit canonical Provider profile'):
        provider_bundle(configuration, artifacts)


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


def test_presend_failure_recovers_only_through_an_explicit_new_task(tmp_path):
    with loopback_provider(tmp_path,'text') as (server,ca):
        port=server.server_port
        configuration,artifacts=provider_inputs(port)
        bundle,publisher=provider_bundle(configuration,artifacts)
        manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        # The profile points at a port with no listener when Task A runs.
        server.shutdown(); server.server_close()
        with daemon_process(tmp_path,publishers=[publisher],label='retry-policy',controlled_provider_test_ca=ca) as owner:
            data=owner.data_dir
            authority=create_actor(data,permissions=['artifact.put','task.submit','model.invoke','capability.invoke'])
            async def presend():
                client=await connect(data,authority=authority)
                try:
                    await prepare_provider(data,authority,bundle,manifest,configuration)
                    uploaded=await client.put_artifact(realm_id='realm://main',actor_id=authority.actor_id,
                        content=canonical_json({'provider':'messages','value':'retry policy recovery'}),kind='task_input',media_type='application/json')
                    task=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                        input_artifact_id=uploaded['artifact_id'],budget={'max_cost_microunits':100000})
                    result,done=await client.wait_task(task.task_id,timeout_s=30)
                    assert done and result['status']=='FAILED' and result['error']=='BACKEND_UNAVAILABLE',result
                    execution=await client.get_task_execution(task.task_id)
                    assert execution['invocations'][0]['provider']['settlement']['outcome']=='NOT_SENT'
                    return uploaded['artifact_id'],task.task_id,execution['invocations'][0]['invocation_id']
                finally:
                    await client.aclose()
            input_ref,task_a_id,invocation_id=asyncio.run(presend())
            # The endpoint returns on the same port with the profile unchanged;
            # recovery is possible only for work explicitly submitted now.
            listener=Server(('127.0.0.1',port),Handler)
            listener.mode,listener.requests,listener.authorized='text',[],[]
            listener.received,listener.peer_closed=threading.Event(),threading.Event()
            listener.release=threading.Event()
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(tmp_path/'test-ca.pem',tmp_path/'test-server.key')
            listener.socket=context.wrap_socket(listener.socket,server_side=True)
            thread=threading.Thread(target=listener.serve_forever,kwargs={'poll_interval':.01},daemon=True); thread.start()
            try:
                async def recover():
                    client=await connect(data,authority=authority)
                    try:
                        replay=await client.get_task_execution(task_a_id)
                        assert replay['invocations'][0]['invocation_id']==invocation_id
                        assert replay['invocations'][0]['provider']['settlement']['outcome']=='NOT_SENT'
                        assert replay['invocations'][0]['provider']['settlement']['liability_microunits']==0
                        fresh=await client.submit_task(realm_id='realm://main',actor_id=authority.actor_id,
                            input_artifact_id=input_ref,budget={'max_cost_microunits':100000})
                        terminal,done=await client.wait_task(fresh.task_id,timeout_s=30)
                        assert done and terminal['status']=='SUCCEEDED',terminal
                        execution=await client.get_task_execution(fresh.task_id)
                        assert len(execution['invocations'])==1 and execution['invocations'][0]['status']=='SUCCEEDED'
                        accounting=execution['invocations'][0]['provider']
                        assert accounting['settlement']['outcome']=='CONFIRMED'
                        assert accounting['settlement']['usage']['cost_microunits']>0
                        assert accounting['terminal']['state']=='RESPONSE' and accounting['terminal']['http_status']==200
                        # Exactly one authorized wire request exists: Task B's own.
                        # Task A's request was never resent against the live listener.
                        assert len(listener.requests)==1 and all(listener.authorized)
                        settled=await client.get_task_execution(task_a_id)
                        assert settled['invocations'][0]['invocation_id']==invocation_id
                        assert settled['invocations'][0]['provider']['settlement']['outcome']=='NOT_SENT'
                        assert settled['status']=='FAILED' and settled['error']=='BACKEND_UNAVAILABLE'
                        assert settled['consumed_budget']['cost_microunits']==0
                    finally:
                        await client.aclose()
                asyncio.run(recover())
            finally:
                listener.shutdown(); listener.server_close(); thread.join(timeout=3)
