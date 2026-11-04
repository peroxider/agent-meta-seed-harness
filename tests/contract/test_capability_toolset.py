"""Signed tools declarations and fail-closed behavior over the installed Host."""
import asyncio
import json

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json, decode_package, sha256_hex
from agent_meta_seed_harness.packaging import TOOLS_EXECUTION_SOURCE_PATHS
from agent_meta_seed_harness.toolset import OPERATIONS
from seed_package import seed_bundle
from seed_actor import create_actor
from toolset_runtime import REALM, tools_environment, submit_tools, upload


def test_signed_tools_package_has_exact_source_closure_and_scoped_declarations():
    bundle, _ = seed_bundle(tools=True)
    assert seed_bundle(tools=True)[0] == bundle
    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    package, source = decode_package(bundle.artifacts[bundle.package_artifact_id])
    assert set(source) == set(TOOLS_EXECUTION_SOURCE_PATHS)
    assert package.package.entrypoint == 'agent_meta_seed_harness.host_binding_tools:create'
    assert manifest['public_api_range'] == '>=1.15.0 <2.0.0'
    descriptors = [json.loads(bundle.artifacts[ref]) for ref in manifest['capability_descriptor_artifact_ids']]
    operations = {op['operation_id']:op for desc in descriptors for op in desc['operations']}
    assert set(OPERATIONS) <= set(operations)
    assert {op['resource_contract'] for op in operations.values() if 'resource_contract' in op} == {
        'artifact.read/v1','artifact.put/v1','state.read/v1','state.write/v1',
        'scratch.create/v1','scratch.execute/v1','scratch.bindings/v1','scratch.inspect/v1','scratch.export/v1','scratch.release/v1'}
    assert operations['seed.transform.normalize_json']['idempotency'] == 'PURE'
    assert operations['seed.state.write']['idempotency'] == 'KEYED'
    requests = json.loads(bundle.artifacts[manifest['grant_requests_artifact_id']])['requests']
    assert not any(target['type'] == 'REALM_ALL' for request in requests for target in request['scope']['targets'])
    assert {request['permission'] for request in requests if request['permission'].startswith('scratch.')} == {
        'scratch.create','scratch.execute','scratch.inspect','scratch.export','scratch.release'}
    assert all(request['scope']['targets'] == [{'type':'CAPABILITY','id':'capability://seed.scratch'}]
        for request in requests if request['permission'].startswith('scratch.'))


@pytest.mark.parametrize('mode', ['unknown','schema','cas','budget','protected','protected_write','source_kind','actor_deny','free_text'])
def test_tools_refuse_undeclared_invalid_conflicting_or_unscoped_effects(tmp_path, mode):
    with tools_environment(tmp_path) as (owner, actor, state, replacement):
        data = owner.data_dir
        submitter = create_actor(data, permissions=['artifact.put','task.submit','model.invoke','capability.invoke','state.read']) if mode == 'actor_deny' else actor
        async def run():
            client = await connect(data, authority=actor)
            task_client = await connect(data, authority=submitter)
            try:
                name, arguments = 'seed.state.write', {'state_id':state['state_id'],
                    'expected_state_revision_id':state['state_revision_id'], 'content_artifact_id':replacement}
                if mode == 'unknown':
                    name, arguments = 'seed.unknown', {}
                elif mode == 'schema':
                    name, arguments = 'seed.artifact.put', {'value':{},'path':'forbidden'}
                elif mode == 'cas':
                    arguments['expected_state_revision_id'] = 'state-revision://01900000-0000-7000-8000-000000000001'
                elif mode == 'protected':
                    protected = (await client.create_state(realm_id=REALM, actor_id=actor.actor_id,
                        owner_id='capability://seed.state', schema_id=state['schema_id'],
                        content_artifact_id=state['content_artifact_id'], purpose='SESSION_TRANSCRIPT')).resource
                    name, arguments = 'seed.state.read', {'state_id':protected['state_id']}
                elif mode == 'protected_write':
                    protected = (await client.create_state(realm_id=REALM, actor_id=actor.actor_id,
                        owner_id='capability://seed.state', schema_id=state['schema_id'],
                        content_artifact_id=state['content_artifact_id'], purpose='SESSION_TRANSCRIPT')).resource
                    arguments = {'state_id':protected['state_id'],
                        'expected_state_revision_id':protected['state_revision_id'], 'content_artifact_id':replacement}
                elif mode == 'source_kind':
                    foreign = await upload(client, actor, {'value':'forbidden kind'}, 'note')
                    name, arguments = 'seed.artifact.read', {'artifact_id':foreign}
                task, terminal, execution = await submit_tools(task_client, submitter, [{'name':name,'arguments':arguments}],
                    scenario='free_text' if mode == 'free_text' else 'tools', budget={'max_steps':1} if mode == 'budget' else None)
                if mode == 'free_text':
                    assert terminal['status'] == 'SUCCEEDED' and len(execution['invocations']) == 1
                else:
                    assert terminal['error'] == {'unknown':'AUTHORITY_DENIED','schema':'INVALID_RESULT',
                        'cas':'REVISION_CONFLICT','budget':'RESOURCE_EXHAUSTED','protected':'AUTHORITY_DENIED',
                        'protected_write':'AUTHORITY_DENIED','source_kind':'AUTHORITY_DENIED','actor_deny':'AUTHORITY_DENIED'}[mode], terminal
                current = await client.get_state(realm_id=REALM, actor_id=actor.actor_id, state_id=state['state_id'])
                assert current['cas_revision'] == 1 and current['state_revision_id'] == state['state_revision_id']
                if mode in ('protected', 'protected_write'):
                    guarded = await client.get_state(realm_id=REALM, actor_id=actor.actor_id, state_id=protected['state_id'])
                    assert guarded['cas_revision'] == 1 and guarded['state_revision_id'] == protected['state_revision_id']
            finally:
                await task_client.aclose()
                await client.aclose()
        asyncio.run(run())


def test_artifact_put_replays_same_payload_receipt_and_refuses_over_boundary(tmp_path):
    with tools_environment(tmp_path) as (owner, actor, state, replacement):
        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                value = {'answer':42, 'secret':'PUT_CANARY'}
                task, terminal, execution = await submit_tools(client, actor, [
                    {'name':'seed.artifact.put','arguments':{'value':value}},
                    {'name':'seed.artifact.put','arguments':{'value':value}}])
                assert terminal['status'] == 'SUCCEEDED', terminal
                left = json.loads(await client.get_artifact_content(execution['invocations'][1]['output_artifact_id']))
                right = json.loads(await client.get_artifact_content(execution['invocations'][2]['output_artifact_id']))
                assert left == right and left['size_bytes'] == len(canonical_json({'answer':42, 'secret':'[REDACTED]'}))
                assert left['sha256'] == sha256_hex(canonical_json({'answer':42, 'secret':'[REDACTED]'}))
                assert json.loads(await client.get_artifact_content(left['artifact_id'])) == {'answer':42, 'secret':'[REDACTED]'}
                _, boundary, execution = await submit_tools(client, actor, [
                    {'name':'seed.artifact.put','arguments':{'value':{'blob':'x'*1048576}}}])
                assert boundary['status'] == 'FAILED' and boundary['error'] == 'FAILED_PRECONDITION', boundary
                assert execution['invocations'] == []
            finally:
                await client.aclose()
        asyncio.run(run())


@pytest.mark.parametrize('json_argument,error,capability', [(42, 'INVALID_RESULT', False), ('{"a":1,"a":2}', 'INVALID_ARGUMENT', True)])
def test_transform_refuses_schema_violations_and_duplicate_json_fields(tmp_path, json_argument, error, capability):
    with tools_environment(tmp_path) as (owner, actor, state, replacement):
        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                _, terminal, execution = await submit_tools(client, actor, [
                    {'name':'seed.transform.normalize_json','arguments':{'json':json_argument}}])
                assert terminal['status'] == 'FAILED' and terminal['error'] == error, terminal
                kinds = ['MODEL', 'CAPABILITY'] if capability else ['MODEL']
                assert [row['kind'] for row in execution['invocations']] == kinds
                if capability:
                    assert execution['invocations'][1]['status'] == 'FAILED'
                    assert execution['invocations'][1]['output_artifact_id'] is None
            finally:
                await client.aclose()
        asyncio.run(run())
