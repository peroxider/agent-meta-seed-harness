"""Controlled TEST loopback only: typed Provider call reaches the resource Host."""
import asyncio
import json
import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json
from agent_meta_seed_harness.toolset import OPERATIONS
from provider_host_fixture import BUSINESS_PROTOCOL_WORDS, loopback_provider, provider_inputs, provider_bundle, provision
from seed_actor import create_actor
from seed_package import activate_seed, wait_ready
from seed_runtime import admin, daemon_process
from toolset_runtime import REALM, PERMISSIONS, upload


@pytest.mark.parametrize('mode',['resource_tools','resource_business_fields'])
def test_synthetic_provider_dispatches_signed_resource_tool_and_receives_public_receipt(tmp_path,mode):
    with loopback_provider(tmp_path, mode) as (server, ca):
        configuration, artifacts = provider_inputs(server.server_port)
        bundle, publisher = provider_bundle(configuration, artifacts, tools=True)
        with daemon_process(tmp_path, publishers=[publisher], controlled_provider_test_ca=ca) as owner:
            actor = create_actor(owner.data_dir, permissions=PERMISSIONS)
            async def run():
                client = await connect(owner.data_dir, authority=actor)
                try:
                    for reference, raw in sorted(bundle.artifacts.items()):
                        result = await client.put_artifact(realm_id=REALM, actor_id=actor.actor_id, content=raw,
                            kind='code', media_type='application/octet-stream')
                        assert result['artifact_id'] == reference
                    report = await client.validate_harness_package(bundle.manifest_artifact_id)
                    assert report['valid'], report
                    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
                    installed = await asyncio.to_thread(admin, owner.data_dir, 'harness', 'install', '--name', manifest['package_name'],
                        '--version', manifest['package_version'], bundle.manifest_artifact_id, bundle.package_artifact_id)
                    handle = await asyncio.to_thread(provision, owner.data_dir)
                    await asyncio.to_thread(admin, owner.data_dir, 'harness', 'configure-provider', installed['harness_id'],
                        '--capability', 'capability://seed.messages-model', '--profile-artifact', configuration['profile_artifact_id'], '--credential-handle', handle)
                    await asyncio.to_thread(activate_seed, owner.data_dir, bundle, installed['harness_id'])
                    await wait_ready(owner.data_dir)
                    reference = await upload(client, actor, {'provider':'messages','value':'synthetic tools integration'}, 'task_input')
                    task = await client.submit_task(realm_id=REALM, actor_id=actor.actor_id, input_artifact_id=reference,
                        budget={'max_cost_microunits':100000})
                    terminal, done = await client.wait_task(task.task_id, timeout_s=20)
                    assert done and terminal['status'] == 'SUCCEEDED', terminal
                    execution = await client.get_task_execution(task.task_id)
                    assert [row['kind'] for row in execution['invocations']] == ['MODEL','CAPABILITY','MODEL']
                    assert len(server.requests) == 2 and all(server.authorized)
                    assert set(OPERATIONS) <= {tool['name'] for tool in server.requests[0]['tools']}
                    tool = execution['invocations'][1]
                    result = json.loads(await client.get_artifact_content(tool['output_artifact_id']))
                    expected=(BUSINESS_PROTOCOL_WORDS if mode=='resource_business_fields' else {
                        'from':'synthetic-provider','secret':'[REDACTED]'})
                    assert json.loads(await client.get_artifact_content(result['artifact_id'])) == expected
                    assert b'SYNTHETIC_PROVIDER_TOOL_CANARY' not in await client.get_artifact_content(tool['input_artifact_id'])
                    messages = server.requests[1]['messages']
                    assert any(part.get('type')=='tool_result' for message in messages if isinstance(message['content'], list) for part in message['content'])
                    if mode=='resource_business_fields':
                        arguments=[part['input'] for message in messages if isinstance(message['content'],list)
                            for part in message['content'] if part.get('type')=='tool_use']
                        assert arguments==[{'value':BUSINESS_PROTOCOL_WORDS}]
                        assert execution['consumed_budget']['cost_microunits']==sum(
                            len(canonical_json({key:request[key] for key in ('messages','system','tools','tool_choice') if key in request}))+2
                            for request in server.requests)
                finally:
                    await client.aclose()
            asyncio.run(run())
