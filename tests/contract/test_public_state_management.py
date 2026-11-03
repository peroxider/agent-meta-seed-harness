"""Independent State consumer: installed SDK, native CLI and owned processes.

The loss test drops a committed response at the public Transport boundary and
kills the owned daemon. It proves post-commit replay, not an in-commit crash.
No Runtime implementation, database, CAS directory or operator key is read.
"""
import asyncio
import json

import pytest

from agent_meta_runtime.sdk import AgentMetaClient, LocalTransport, StableError, connect
from agent_meta_runtime.sdk.packages import canonical_json
from agent_meta_runtime.sdk.transport import LocalConnection
from seed_actor import create_actor
from seed_package import seed_bundle
from seed_runtime import admin, daemon_process

REALM = 'realm://main'
OWNER = 'capability://seed.echo'
WRITE = 'agent_meta.public.v1.State.Write'
READ = 'agent_meta.public.v1.State.Get'
PERMISSIONS = ['artifact.put', 'capability.invoke', 'state.read', 'state.write']


async def upload(client, authority, value, *, kind='seed_content'):
    return (await client.put_artifact(realm_id=REALM, actor_id=authority.actor_id,
        content=canonical_json(value), kind=kind, media_type='application/json'))['artifact_id']


async def install(data, authority, bundle):
    client = await connect(data, authority=authority)
    try:
        for reference, raw in sorted(bundle.artifacts.items()):
            result = await client.put_artifact(realm_id=REALM, actor_id=authority.actor_id,
                content=raw, kind='code', media_type='application/octet-stream')
            assert result['artifact_id'] == reference
        assert (await client.validate_harness_package(bundle.manifest_artifact_id))['valid']
        manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        # State initialization is deliberately before activation.
        await asyncio.to_thread(admin, data, 'harness', 'install', '--name', manifest['package_name'],
            '--version', manifest['package_version'], bundle.manifest_artifact_id, bundle.package_artifact_id)
    finally:
        await client.aclose()


async def initialized(client, authority, *, purpose='GENERAL'):
    schema = await upload(client, authority, {'type': 'object', 'required': ['value'],
        'properties': {'value': {'type': 'integer'}, 'secret': {'type': 'string'}},
        'additionalProperties': False}, kind='schema')
    content = await upload(client, authority, {'value': 1, 'secret': 'SEED_STATE_CANARY'})
    return (await client.create_state(realm_id=REALM, actor_id=authority.actor_id, owner_id=OWNER,
        schema_id=schema, content_artifact_id=content, purpose=purpose)).resource


@pytest.fixture
def state_environment(tmp_path):
    bundle, publisher = seed_bundle()
    with daemon_process(tmp_path, publishers=[publisher]) as owner:
        authority = create_actor(owner.data_dir, permissions=PERMISSIONS)
        asyncio.run(install(owner.data_dir, authority, bundle))
        yield owner.data_dir, authority


def test_state_lifecycle_redaction_history_and_conflict_use_public_commands(state_environment):
    data, authority = state_environment
    async def run():
        client = await connect(data, authority=authority)
        try:
            initial = await initialized(client, authority)
            assert initial['cas_revision'] == 1 and initial['controller_principal_id'] == authority.actor_id
            assert json.loads(await client.get_artifact_content(initial['content_artifact_id'])) == {
                'value': 1, 'secret': '[REDACTED]'}
            replacement = await upload(client, authority, {'value': 2})
            command = client.build_state_write(realm_id=REALM, actor_id=authority.actor_id,
                state_id=initial['state_id'], expected_state_revision_id=initial['state_revision_id'],
                expected_cas_revision=1, schema_id=initial['schema_id'], content_artifact_id=replacement)
            changed = await client.execute_command(WRITE, command)
            assert changed.resource['cas_revision'] == 2
            assert changed.resource['content_artifact_id'] == replacement
            assert await client.execute_command(WRITE, command) == changed
            historical = await client.get_state(realm_id=REALM, actor_id=authority.actor_id,
                state_id=initial['state_id'], state_revision_id=initial['state_revision_id'])
            assert historical['content_artifact_id'] == initial['content_artifact_id']
            assert historical['current_revision_id'] == changed.resource['state_revision_id']
            assert historical['cas_revision'] == 2
            with pytest.raises(StableError) as conflict:
                await client.write_state(realm_id=REALM, actor_id=authority.actor_id,
                    state_id=initial['state_id'], expected_state_revision_id=initial['state_revision_id'],
                    expected_cas_revision=1, schema_id=initial['schema_id'], content_artifact_id=replacement)
            assert conflict.value.code == 'REVISION_CONFLICT'
            invalid = await upload(client, authority, {'value': 'wrong scalar'})
            with pytest.raises(StableError) as schema:
                await client.write_state(realm_id=REALM, actor_id=authority.actor_id,
                    state_id=initial['state_id'], expected_state_revision_id=changed.resource['state_revision_id'],
                    expected_cas_revision=2, schema_id=initial['schema_id'], content_artifact_id=invalid)
            assert schema.value.code == 'INVALID_ARGUMENT'
            current = await client.get_state(realm_id=REALM, actor_id=authority.actor_id, state_id=initial['state_id'])
            assert current['cas_revision'] == 2 and current['state_revision_id'] == changed.resource['state_revision_id']
        finally:
            await client.aclose()
    asyncio.run(run())


def test_session_state_controller_cannot_be_bypassed_by_another_actor(state_environment):
    data, authority = state_environment
    other = create_actor(data, permissions=['state.read', 'state.write', 'capability.invoke'])
    async def run():
        client = await connect(data, authority=authority)
        outsider = await connect(data, authority=other)
        try:
            initial = await initialized(client, authority, purpose='SESSION_JOURNAL')
            for operation in ('read', 'write'):
                with pytest.raises(StableError) as denied:
                    if operation == 'read':
                        await outsider.get_state(realm_id=REALM, actor_id=other.actor_id, state_id=initial['state_id'])
                    else:
                        await outsider.write_state(realm_id=REALM, actor_id=other.actor_id,
                            state_id=initial['state_id'], expected_state_revision_id=initial['state_revision_id'],
                            expected_cas_revision=1, schema_id=initial['schema_id'],
                            content_artifact_id=initial['content_artifact_id'])
                assert denied.value.code == 'AUTHORITY_DENIED'
            current = await client.get_state(realm_id=REALM, actor_id=authority.actor_id, state_id=initial['state_id'])
            assert current['cas_revision'] == 1 and current['purpose'] == 'SESSION_JOURNAL'
        finally:
            await outsider.aclose()
            await client.aclose()
    asyncio.run(run())


def test_audited_read_receipt_replays_without_another_grant_use(state_environment):
    data, authority = state_environment
    reader = create_actor(data, permissions=['state.read'], max_uses=1)
    async def run():
        client = await connect(data, authority=authority)
        limited = await connect(data, authority=reader)
        try:
            initial = await initialized(client, authority)
            command = limited.build_state_read(realm_id=REALM, actor_id=reader.actor_id, state_id=initial['state_id'])
            first = await limited.execute_command(READ, command)
            replacement = await upload(client, authority, {'value': 2})
            await client.write_state(realm_id=REALM, actor_id=authority.actor_id,
                state_id=initial['state_id'], expected_state_revision_id=initial['state_revision_id'],
                expected_cas_revision=1, schema_id=initial['schema_id'], content_artifact_id=replacement)
            assert await limited.execute_command(READ, command) == first
            assert first.resource['cas_revision'] == 1
            with pytest.raises(StableError) as exhausted:
                await limited.get_state(realm_id=REALM, actor_id=reader.actor_id, state_id=initial['state_id'])
            assert exhausted.value.code == 'AUTHORITY_DENIED'
        finally:
            await limited.aclose()
            await client.aclose()
    asyncio.run(run())


class DropCommittedWrite:
    """Fault at the consumer Transport return boundary, before SDK decoding."""
    def __init__(self, delegate, process):
        self.delegate, self.process = delegate, process
        self.dropped = False

    async def call(self, method, request, *, deadline_us=None):
        response = await self.delegate.call(method, request, deadline_us=deadline_us)
        if method == WRITE and not self.dropped:
            self.dropped = True
            self.process.kill()
            self.process.wait(timeout=10)
            raise ConnectionError('consumer fault: committed State.Write response discarded')
        return response

    async def close(self):
        await self.delegate.close()


def test_lost_write_response_and_owned_daemon_kill_replay_exact_command(tmp_path):
    bundle, publisher = seed_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label='before-loss') as owner:
        authority = create_actor(owner.data_dir, permissions=PERMISSIONS)
        asyncio.run(install(owner.data_dir, authority, bundle))
        async def lose_response():
            connection = LocalConnection(owner.data_dir / 'run/agent-meta.sock')
            await connection.connect()
            fault = DropCommittedWrite(LocalTransport(connection), owner.process)
            client = AgentMetaClient(fault, authority=authority)
            try:
                initial = await initialized(client, authority)
                replacement = await upload(client, authority, {'value': 2})
                command = client.build_state_write(realm_id=REALM, actor_id=authority.actor_id,
                    state_id=initial['state_id'], expected_state_revision_id=initial['state_revision_id'],
                    expected_cas_revision=1, schema_id=initial['schema_id'], content_artifact_id=replacement)
                with pytest.raises(ConnectionError, match='response discarded'):
                    await client.execute_command(WRITE, command)
                assert fault.dropped and owner.process.poll() is not None
                return initial, replacement, command
            finally:
                await client.aclose()
        initial, replacement, command = asyncio.run(lose_response())
    with daemon_process(tmp_path, publishers=[publisher], label='after-loss') as recovered:
        async def replay():
            client = await connect(recovered.data_dir, authority=authority)
            try:
                receipt = await client.execute_command(WRITE, command)
                assert receipt.resource['cas_revision'] == 2 and receipt.resource['content_artifact_id'] == replacement
                assert await client.execute_command(WRITE, command) == receipt
                current = await client.get_state(realm_id=REALM, actor_id=authority.actor_id, state_id=initial['state_id'])
                assert current['cas_revision'] == 2 and current['state_revision_id'] == receipt.resource['state_revision_id']
            finally:
                await client.aclose()
        asyncio.run(replay())
