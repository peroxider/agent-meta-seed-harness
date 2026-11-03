"""Native public process setup for the independent signed tools consumer."""
import asyncio
from contextlib import contextmanager
import json

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json
from seed_actor import create_actor
from seed_package import activate_seed, seed_bundle, wait_ready
from seed_runtime import admin, daemon_process

REALM = 'realm://main'
PERMISSIONS = ['artifact.put', 'task.submit', 'model.invoke', 'capability.invoke', 'state.read', 'state.write',
    'scratch.create', 'scratch.execute', 'scratch.inspect', 'scratch.export', 'scratch.release']


async def upload(client, actor, value, kind='seed_content'):
    return (await client.put_artifact(realm_id=REALM, actor_id=actor.actor_id, content=canonical_json(value),
        kind=kind, media_type='application/json'))['artifact_id']


@contextmanager
def tools_environment(root, *, overrides=None, execution_backend=None, actor_permissions=None):
    bundle, publisher = seed_bundle(tools=True, overrides=overrides)
    with daemon_process(root, publishers=[publisher], execution_backend=execution_backend) as owner:
        actor = create_actor(owner.data_dir, permissions=PERMISSIONS if actor_permissions is None else actor_permissions)
        async def setup():
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
                schema = await upload(client, actor, {'type':'object'}, 'schema')
                initial_content = await upload(client, actor, {'value':1})
                replacement = await upload(client, actor, {'value':2})
                initial = (await client.create_state(realm_id=REALM, actor_id=actor.actor_id, owner_id='capability://seed.state',
                    schema_id=schema, content_artifact_id=initial_content)).resource
                await asyncio.to_thread(activate_seed, owner.data_dir, bundle, installed['harness_id'])
                await wait_ready(owner.data_dir)
                return initial, replacement
            finally:
                await client.aclose()
        state, replacement = asyncio.run(setup())
        yield owner, actor, state, replacement


async def submit_tools(client, actor, calls, *, scenario='tools', budget=None):
    reference = await upload(client, actor, {'provider':'fake-tools','calls':calls,'scenario':scenario}, 'task_input')
    task = await client.submit_task(realm_id=REALM, actor_id=actor.actor_id, input_artifact_id=reference,
        **({'budget':budget} if budget is not None else {}))
    terminal, done = await client.wait_task(task.task_id, timeout_s=15)
    assert done, terminal
    return task, terminal, await client.get_task_execution(task.task_id)
