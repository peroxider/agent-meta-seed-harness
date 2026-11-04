"""SH-GOV-02 (partial): operator-approved release governance for the tools package.

The frozen plan's evolution-release proof runs the release drill for the
tools package — the bundle carrying the S07-relevant capability set: an
approved activation cuts serving over, an unhealthy candidate never moves
serving, a drained old version uninstalls terminally, and a rollback is a
fresh approved activation of the old version, not grant resurrection. The
minimal bundle legs are pinned by tests/acceptance/test_release_lifecycle.py
(SH-REL-01); candidate-configuration promotion has no public interface on the
pinned Runtime wheel (RP-06 OPEN) and stays out of scope.
"""
import asyncio

from agent_meta_runtime.sdk import connect
from importlib.resources import files
from seed_actor import create_actor
from seed_package import activate_seed, install_seed, seed_bundle, wait_ready
from seed_runtime import admin, running_daemon
from toolset_runtime import PERMISSIONS, submit_tools


async def refs_at(data_dir, *, serving, status=None):
    client = await connect(data_dir)
    try:
        end = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < end:
            refs = await client.get_refs()
            if refs['serving_revision'] == serving and (status is None or refs['reconcile_status'] == status):
                return refs
            await asyncio.sleep(.01)
        raise AssertionError(f'cutover did not reach the requested state: {refs}')
    finally:
        await client.aclose()


def tools_version_bundle(revision, *, unhealthy=False):
    version = f'0.1.{revision - 1}-dev.1'
    overrides = {}
    if unhealthy:
        binding = files('agent_meta_seed_harness').joinpath('host_binding_tools.py').read_bytes()
        assert b"HealthStatus('READY', 'OFFLINE_TOOLS_ADAPTER_READY')" in binding
        overrides['agent_meta_seed_harness/host_binding_tools.py'] = binding.replace(
            b"HealthStatus('READY', 'OFFLINE_TOOLS_ADAPTER_READY')",
            b"HealthStatus('UNHEALTHY', 'SELF_TEST_FAILED')")
    return seed_bundle(tools=True, overrides=overrides, version=version, descriptor_revision=revision)


async def echo_under(data_dir, actor, calls):
    client = await connect(data_dir, authority=actor)
    try:
        _, terminal, execution = await submit_tools(client, actor, calls)
        assert terminal['status'] == 'SUCCEEDED', terminal
        return execution['serving_composition_id']
    finally:
        await client.aclose()


def test_tools_package_cutover_failed_candidate_and_uninstall(tmp_path):
    first, publisher = tools_version_bundle(1)
    second, _ = tools_version_bundle(2)
    failed, _ = tools_version_bundle(3, unhealthy=True)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        actor = create_actor(data_dir, permissions=PERMISSIONS)
        old_id = install_seed(data_dir, tmp_path, first)
        asyncio.run(wait_ready(data_dir, revision=1))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        failed_id = install_seed(data_dir, tmp_path, failed, activate=False)
        first_composition = asyncio.run(echo_under(data_dir, actor, [{'name': 'seed.echo', 'arguments': {'value': 'v1'}}]))

        # An approved activation cuts serving over to the new version.
        activate_seed(data_dir, second, new_id)
        asyncio.run(refs_at(data_dir, serving=2, status='READY'))
        asyncio.run(wait_ready(data_dir, revision=2))
        second_composition = asyncio.run(echo_under(data_dir, actor, [{'name': 'seed.echo', 'arguments': {'value': 'v2'}}]))
        assert second_composition != first_composition

        # An unhealthy candidate is accepted for install but its activation
        # never realizes: serving stays on the healthy version.
        activate_seed(data_dir, failed, failed_id)
        refs = asyncio.run(refs_at(data_dir, serving=2, status='FAILED'))
        assert refs['desired_revision'] == 3 and refs['realized_revision'] == 2, refs
        asyncio.run(wait_ready(data_dir, revision=2))
        assert admin(data_dir, 'harness', 'inspect', new_id)['status'] == 'ACTIVE'
        assert admin(data_dir, 'harness', 'inspect', failed_id)['status'] == 'INSTALLED'
        assert asyncio.run(echo_under(data_dir, actor, [{'name': 'seed.echo', 'arguments': {'value': 'still-v2'}}])) == second_composition

        # The drained old version is INACTIVE and uninstalls terminally while
        # the active version keeps serving.
        assert admin(data_dir, 'harness', 'inspect', old_id)['status'] == 'INACTIVE'
        admin(data_dir, 'harness', 'uninstall', old_id)
        assert admin(data_dir, 'harness', 'inspect', old_id)['status'] == 'UNINSTALLED'
        assert asyncio.run(echo_under(data_dir, actor, [{'name': 'seed.echo', 'arguments': {'value': 'after-uninstall'}}])) == second_composition


def test_tools_package_rollback_is_a_fresh_approved_activation(tmp_path):
    first, publisher = tools_version_bundle(1)
    second, _ = tools_version_bundle(2)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        actor = create_actor(data_dir, permissions=PERMISSIONS)
        old_id = install_seed(data_dir, tmp_path, first)
        asyncio.run(wait_ready(data_dir, revision=1))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        activate_seed(data_dir, second, new_id)
        asyncio.run(refs_at(data_dir, serving=2, status='READY'))
        cutover_composition = asyncio.run(echo_under(data_dir, actor, [{'name': 'seed.echo', 'arguments': {'value': 'v2'}}]))

        # Rollback is a fresh approved activation of the old version: serving
        # advances to a new revision realizing the old package, grants come
        # from the new envelope, and the receipt is inspectable.
        activate_seed(data_dir, first, old_id)
        asyncio.run(refs_at(data_dir, serving=3, status='READY'))
        asyncio.run(wait_ready(data_dir, revision=3))
        rollback_composition = asyncio.run(echo_under(data_dir, actor, [{'name': 'seed.echo', 'arguments': {'value': 'back-v1'}}]))
        assert rollback_composition != cutover_composition
        assert admin(data_dir, 'harness', 'inspect', old_id)['status'] == 'ACTIVE'
        assert admin(data_dir, 'harness', 'inspect', new_id)['status'] == 'INACTIVE'
