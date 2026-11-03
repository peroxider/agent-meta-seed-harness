"""SH-REL-01: new-version cutover, old Task drain and failed candidate safety."""

import asyncio
from importlib.resources import files
import json
import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

from recovery_runtime import terminal_execution, wait_invocations
from seed_package import activate_seed, install_seed, limit_activation_grant, seed_bundle, wait_ready
from seed_runtime import admin, running_daemon
from seed_runtime import daemon_process
from seed_runtime import invoke


def prepared_activation(data_dir, bundle, harness_id):
    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    requests = json.loads(bundle.artifacts[manifest["grant_requests_artifact_id"]])["requests"]
    flags = [value for request in requests for value in ("--grant", canonical_json(request).decode())]
    return admin(data_dir, "--dry-run", "harness", "activate", harness_id,
        manifest["composition_template_artifact_id"], *flags)["command_envelope_jcs"]


class ObservedTransport:
    """Lose a consumer response only after the real server has returned it."""
    def __init__(self, transport, *, discard=False):
        self.transport, self.discard, self.responses = transport, discard, []

    async def call(self, method, request, *, deadline_us=None):
        result = await self.transport.call(method, request, deadline_us=deadline_us)
        self.responses.append((method, bytes(result)))
        if self.discard:
            self.discard = False
            raise ConnectionError("consumer discarded an actual committed response")
        return result

    async def close(self):
        await self.transport.close()


async def observed_client(data_dir, *, discard=False):
    from agent_meta_runtime.sdk import AgentMetaClient, LocalTransport
    from agent_meta_runtime.sdk.transport import LocalConnection
    connection = LocalConnection(data_dir / "run/agent-meta.sock")
    await connection.connect()
    transport = ObservedTransport(LocalTransport(connection), discard=discard)
    return AgentMetaClient(transport), transport


async def confirmed_execution(data_dir, task_id):
    """Freeze metadata only after any actual Backend acks have settled."""
    client = await connect(data_dir)
    try:
        deadline = asyncio.get_running_loop().time() + 10
        while True:
            execution = await client.get_task_execution(task_id)
            if all(i.get("execution_binding", {}).get("ack_state", "ACKNOWLEDGED") == "ACKNOWLEDGED"
                    for i in execution["invocations"]):
                return execution
            assert asyncio.get_running_loop().time() < deadline, execution
            await asyncio.sleep(.01)
    finally:
        await client.aclose()


PROVIDER = b'''
import asyncio
import json
from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import JsonPart, ModelResponse, ProviderUsage, ToolCallPart
from agent_meta_runtime.sdk.packages import canonical_json

async def invoke_fake(request):
    if request.ordinal == 0:
        if json.loads(rendered_sections(request.projection)["task_input"])["scenario"] == "late_tool":
            await asyncio.sleep(4)
        return ModelResponse((ToolCallPart("echo-0", "seed.echo", canonical_json({"value": "__PACKAGE_VERSION__"}).decode()),), "TOOL_CALL", ProviderUsage(None, None, 0))
    history = json.loads(request.history_content)
    assert json.loads(bytes.fromhex(history[1]["content_hex"])) == {"value": "__PACKAGE_VERSION__"}
    return ModelResponse((JsonPart({"package_version": "__PACKAGE_VERSION__", "composition_id": request.task.serving_composition_id,
        "accepted_meta_revision": request.task.accepted_meta_revision, "input_artifact_id": request.task.input_artifact_id}),), "STOP", ProviderUsage(None, None, 0))
'''

LOOP = b'''
import asyncio
import json
from agent_meta_runtime.sdk.host import ToolCallPart, terminal_result
from .context import project

async def run_task(task, host):
    response = await host.invoke_model(await project(task, host))
    for call in response.parts:
        if isinstance(call, ToolCallPart):
            await host.invoke_tool(call)
    response = await host.invoke_model(await project(task, host))
    if json.loads(task.input_content)["scenario"] == "slow":
        await asyncio.sleep(4)
    return terminal_result(response)
'''


def version_bundle(revision, *, unhealthy=False, descriptor_revision=None):
    version = f"0.1.{revision - 1}-dev.1"
    overrides = {"agent_meta_seed_harness/providers/fake.py": PROVIDER.replace(b"__PACKAGE_VERSION__", version.encode()),
        "agent_meta_seed_harness/loop.py": LOOP}
    if unhealthy:
        binding = files("agent_meta_seed_harness").joinpath("host_binding.py").read_bytes()
        assert b'HealthStatus("READY", "OFFLINE_ADAPTER_READY")' in binding
        overrides["agent_meta_seed_harness/host_binding.py"] = binding.replace(
            b'HealthStatus("READY", "OFFLINE_ADAPTER_READY")', b'HealthStatus("UNHEALTHY", "SELF_TEST_FAILED")')
    return seed_bundle(overrides=overrides, version=version,
        descriptor_revision=descriptor_revision or revision)


def submit(data_dir, root, scenario):
    path = root / "input.json"
    path.write_bytes(canonical_json({"provider": "fake", "scenario": scenario, "value": "fixture"}))
    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
    return admin(data_dir, "task", "submit", "--input-artifact", reference)["task_id"]


async def refs_at(data_dir, *, serving, status=None):
    client = await connect(data_dir)
    try:
        end = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < end:
            refs = await client.get_refs()
            if refs["serving_revision"] == serving and (status is None or refs["reconcile_status"] == status):
                return refs
            await asyncio.sleep(.01)
        raise AssertionError(f"cutover did not reach the requested state: {refs}")
    finally:
        await client.aclose()


def assert_result(result, execution, *, version, composition_id=None):
    assert result["status"] == "SUCCEEDED", result
    if composition_id is not None:
        assert execution["serving_composition_id"] == composition_id
    expected = TerminalResult((JsonPart({"package_version": version,
        "composition_id": execution["serving_composition_id"], "accepted_meta_revision": execution["accepted_meta_revision"],
        "input_artifact_id": execution["input_artifact_id"]}),))
    assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(encode_terminal_result(expected))
    assert len(execution["invocations"]) == 3


def test_successful_upgrade_drains_frozen_old_task_and_failed_upgrade_preserves_new_serving(tmp_path):
    first, publisher = version_bundle(1)
    second, _ = version_bundle(2)
    failed, _ = version_bundle(3, unhealthy=True)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        old_id = install_seed(data_dir, tmp_path, first)
        asyncio.run(wait_ready(data_dir, revision=1))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        failed_id = install_seed(data_dir, tmp_path, failed, activate=False)
        old_task = submit(data_dir, tmp_path, "slow")
        frozen = asyncio.run(wait_invocations(data_dir, old_task, statuses=["SUCCEEDED", "SUCCEEDED", "SUCCEEDED"]))
        activate_seed(data_dir, second, new_id)
        asyncio.run(refs_at(data_dir, serving=2))
        result, old_execution = asyncio.run(terminal_execution(data_dir, old_task))
        assert_result(result, old_execution, version="0.1.0-dev.1", composition_id=frozen["serving_composition_id"])
        assert old_execution["accepted_meta_revision"] == frozen["accepted_meta_revision"]
        assert old_execution["capability_surface_artifact_id"] == frozen["capability_surface_artifact_id"]
        asyncio.run(wait_ready(data_dir, revision=2))
        asyncio.run(refs_at(data_dir, serving=2, status="READY"))
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "INACTIVE"
        admin(data_dir, "harness", "uninstall", old_id)
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "UNINSTALLED"
        current_task = submit(data_dir, tmp_path, "normal")
        result, current_execution = asyncio.run(terminal_execution(data_dir, current_task))
        assert_result(result, current_execution, version="0.1.1-dev.1")
        assert current_execution["serving_composition_id"] != frozen["serving_composition_id"]
        activate_seed(data_dir, failed, failed_id)
        refs = asyncio.run(refs_at(data_dir, serving=2, status="FAILED"))
        assert refs["desired_revision"] == 3 and refs["realized_revision"] == 2
        asyncio.run(wait_ready(data_dir, revision=2))
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "ACTIVE"
        assert admin(data_dir, "harness", "inspect", failed_id)["status"] == "INSTALLED"
        result, execution = asyncio.run(terminal_execution(data_dir, submit(data_dir, tmp_path, "normal")))
        assert_result(result, execution, version="0.1.1-dev.1", composition_id=current_execution["serving_composition_id"])


def test_superseded_task_cannot_borrow_new_installation_or_root_grants_for_another_tool_call(tmp_path):
    first, publisher = version_bundle(1)
    second, _ = version_bundle(2)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        install_seed(data_dir, tmp_path, first)
        asyncio.run(wait_ready(data_dir, revision=1))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        old_task = submit(data_dir, tmp_path, "late_tool")
        frozen = asyncio.run(wait_invocations(data_dir, old_task, statuses=["RUNNING"]))
        activate_seed(data_dir, second, new_id)
        asyncio.run(refs_at(data_dir, serving=2))
        result, execution = asyncio.run(terminal_execution(data_dir, old_task))
        assert result["status"] == "FAILED" and result["error"] == "AUTHORITY_DENIED", result
        assert execution["serving_composition_id"] == frozen["serving_composition_id"]
        assert execution["capability_surface_artifact_id"] == frozen["capability_surface_artifact_id"]
        assert len(execution["invocations"]) == 1 and execution["invocations"][0]["status"] == "SUCCEEDED"
        assert execution["consumed_budget"]["model_calls"] == execution["consumed_budget"]["steps"] == 1
        asyncio.run(wait_ready(data_dir, revision=2))
        current_result, current_execution = asyncio.run(terminal_execution(data_dir, submit(data_dir, tmp_path, "normal")))
        assert_result(current_result, current_execution, version="0.1.1-dev.1")


@pytest.mark.parametrize("execution_backend", ["trusted_in_process", "in_memory"])
def test_approved_package_rollback_renews_grants_and_replays_lost_activation_after_restart(tmp_path, execution_backend):
    """Stateless package rollback is a fresh approved activation, not grant resurrection."""
    from agent_meta_runtime.sdk import ErrorCode, StableError
    first, publisher = version_bundle(1)
    second, _ = version_bundle(2)
    method = "agent_meta.public.v1.Harness.Activate"
    captured, signed, rollback_task = None, None, None
    with daemon_process(tmp_path, publishers=[publisher], execution_backend=execution_backend, label="before-rollback") as owner:
        data_dir = owner.data_dir
        old_id = install_seed(data_dir, tmp_path, first, activate=False)
        original = activate_seed(data_dir, first, old_id)
        asyncio.run(wait_ready(data_dir, revision=1))
        old_task = submit(data_dir, tmp_path, "normal")
        old_result, old_execution = asyncio.run(terminal_execution(data_dir, old_task))
        assert_result(old_result, old_execution, version="0.1.0-dev.1")
        old_execution = asyncio.run(confirmed_execution(data_dir, old_task))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        upgraded = activate_seed(data_dir, second, new_id)
        asyncio.run(wait_ready(data_dir, revision=2))
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "INACTIVE"
        stale = prepared_activation(data_dir, first, old_id)
        # An ordinary public mutation makes the signed observation stale.
        file = tmp_path / "change-meta.txt"
        file.write_text("explicit public revision change")
        admin(data_dir, "artifact", "put", str(file), "--kind", "code")
        async def rejected():
            client, _transport = await observed_client(data_dir)
            try:
                with pytest.raises(StableError) as error:
                    await client.execute_command(method, stale)
                assert error.value.code == ErrorCode.REVISION_CONFLICT
            finally:
                await client.aclose()
        asyncio.run(rejected())
        assert admin(data_dir, "refs")["serving_revision"] == 2
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "ACTIVE"
        signed = prepared_activation(data_dir, first, old_id)
        async def response_lost():
            client, transport = await observed_client(data_dir, discard=True)
            try:
                with pytest.raises(ConnectionError, match="discarded"):
                    await client.execute_command(method, signed)
                assert len(transport.responses) == 1 and transport.responses[0][0] == method
                return transport.responses[0][1]
            finally:
                await client.aclose()
        captured = asyncio.run(response_lost())
        asyncio.run(wait_ready(data_dir, revision=3))
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "ACTIVE"
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "INACTIVE"
        rollback_task = submit(data_dir, tmp_path, "normal")
        result, execution = asyncio.run(terminal_execution(data_dir, rollback_task))
        assert_result(result, execution, version="0.1.0-dev.1")
        assert execution["serving_composition_id"] not in (old_execution["serving_composition_id"], upgraded["composition_id"])
        assert execution["serving_revision"] == 3
    # A fresh real owner must return the original receipt/resource before
    # revalidating the now-stale plan or allocating another grant generation.
    with daemon_process(tmp_path, publishers=[publisher], execution_backend=execution_backend, label="after-rollback") as owner:
        data_dir = owner.data_dir
        asyncio.run(wait_ready(data_dir, revision=3))
        async def replayed():
            client, transport = await observed_client(data_dir)
            try:
                before = await client.get_refs()
                first_replay = await client.execute_command(method, signed)
                first_raw = transport.responses[-1][1]
                second_replay = await client.execute_command(method, signed)
                second_raw = transport.responses[-1][1]
                assert first_raw == second_raw == captured
                assert first_replay == second_replay
                assert first_replay.resource["revision"] == 3
                assert set(first_replay.resource["grant_ids"]).isdisjoint(original["grant_ids"])
                assert set(first_replay.resource["grant_ids"]).isdisjoint(upgraded["grant_ids"])
                after = await client.get_refs()
                assert all(before[key] == after[key] == 3 for key in ("desired_revision", "serving_revision", "realized_revision"))
                preserved = await client.get_task_execution(old_task)
                assert preserved["result_artifact_id"] == old_execution["result_artifact_id"]
                assert preserved["invocations"] == old_execution["invocations"]
            finally:
                await client.aclose()
        asyncio.run(replayed())
        result, execution = asyncio.run(terminal_execution(data_dir, submit(data_dir, tmp_path, "normal")))
        assert_result(result, execution, version="0.1.0-dev.1")
        admin(data_dir, "harness", "uninstall", new_id)
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "UNINSTALLED"
        manifest = json.loads(second.artifacts[second.manifest_artifact_id])
        requests = json.loads(second.artifacts[manifest["grant_requests_artifact_id"]])["requests"]
        flags = [value for request in requests for value in ("--grant", canonical_json(request).decode())]
        failed, envelope = invoke(data_dir, "harness", "activate", new_id, manifest["composition_template_artifact_id"], *flags)
        assert failed.returncode != 0 and envelope["error"]["code"] == "FAILED_PRECONDITION", envelope
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "UNINSTALLED"
        assert admin(data_dir, "refs")["serving_revision"] == 3


def test_rollback_drains_midflight_new_version_task_under_frozen_composition(tmp_path):
    first, publisher = version_bundle(1)
    second, _ = version_bundle(2)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        old_id = install_seed(data_dir, tmp_path, first, activate=False)
        activate_seed(data_dir, first, old_id)
        asyncio.run(wait_ready(data_dir, revision=1))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        activate_seed(data_dir, second, new_id)
        asyncio.run(wait_ready(data_dir, revision=2))
        flight_task = submit(data_dir, tmp_path, "slow")
        frozen = asyncio.run(wait_invocations(data_dir, flight_task,
            statuses=["SUCCEEDED", "SUCCEEDED", "SUCCEEDED"]))
        # The rollback activates the old package while the new-version Task
        # is still between its confirmed results and its terminal.
        activate_seed(data_dir, first, old_id)
        asyncio.run(refs_at(data_dir, serving=3))
        result, execution = asyncio.run(terminal_execution(data_dir, flight_task))
        assert_result(result, execution, version="0.1.1-dev.1",
            composition_id=frozen["serving_composition_id"])
        assert execution["accepted_meta_revision"] == frozen["accepted_meta_revision"]
        result, execution = asyncio.run(terminal_execution(data_dir,
            submit(data_dir, tmp_path, "normal")))
        assert_result(result, execution, version="0.1.0-dev.1")
        assert execution["serving_revision"] == 3
        assert execution["serving_composition_id"] != frozen["serving_composition_id"]


def test_rollback_mints_fresh_limited_grants_and_never_falls_back_after_denial(tmp_path):
    from agent_meta_runtime.sdk import connect
    first, publisher = version_bundle(1)
    limited = limit_activation_grant(first, permission="capability.invoke", max_uses=1)
    second, _ = version_bundle(2)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        old_id = install_seed(data_dir, tmp_path, limited, activate=False)
        activate_seed(data_dir, limited, old_id)
        asyncio.run(wait_ready(data_dir, revision=1))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        activate_seed(data_dir, second, new_id)
        asyncio.run(wait_ready(data_dir, revision=2))
        # Rollback re-mints the old package's frozen grant requests as a new
        # generation — limits included, nothing resurrected or widened.
        activate_seed(data_dir, limited, old_id)
        asyncio.run(refs_at(data_dir, serving=3))
        drained = submit(data_dir, tmp_path, "normal")
        result, execution = asyncio.run(terminal_execution(data_dir, drained))
        assert_result(result, execution, version="0.1.0-dev.1")
        assert execution["serving_revision"] == 3
        denied = submit(data_dir, tmp_path, "normal")
        async def refused():
            client = await connect(data_dir)
            try:
                result, terminal = await client.wait_task(denied, timeout_s=10)
                assert terminal and result["status"] == "FAILED", result
                assert result["error"] == "AUTHORITY_DENIED", result
                after = await client.get_task_execution(denied)
                assert [item["status"] for item in after["invocations"]] == ["SUCCEEDED"]
                assert after["consumed_budget"]["model_calls"] == 1
                assert (await client.get_refs())["serving_revision"] == 3
            finally:
                await client.aclose()
        asyncio.run(refused())
        # The denial never triggers a fallback or reactivation: the rolled
        # back package keeps serving with its own exhausted grant generation.
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "ACTIVE"
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "INACTIVE"
        assert admin(data_dir, "refs")["serving_revision"] == 3


def test_uninstalled_package_is_terminal_for_rollback_reinstall_and_serving_uninstall(tmp_path):
    first, publisher = version_bundle(1)
    second, _ = version_bundle(2)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        old_id = install_seed(data_dir, tmp_path, first, activate=False)
        activate_seed(data_dir, first, old_id)
        asyncio.run(wait_ready(data_dir, revision=1))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        activate_seed(data_dir, second, new_id)
        asyncio.run(wait_ready(data_dir, revision=2))
        admin(data_dir, "harness", "uninstall", old_id)
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "UNINSTALLED"
        manifest = json.loads(first.artifacts[first.manifest_artifact_id])
        requests = json.loads(first.artifacts[manifest["grant_requests_artifact_id"]])["requests"]
        flags = [value for request in requests for value in ("--grant", canonical_json(request).decode())]
        # A rollback activation of the uninstalled identity is refused; the
        # terminal UNINSTALLED history never revives.
        failed, envelope = invoke(data_dir, "harness", "activate", old_id,
            manifest["composition_template_artifact_id"], *flags)
        assert failed.returncode != 0 and envelope["error"]["code"] == "FAILED_PRECONDITION", envelope
        assert envelope["error"]["details"]["retryable_hint"] == "conditional"
        # Reinstalling the same signed package identity is refused as well.
        failed, envelope = invoke(data_dir, "harness", "install", "--name", manifest["package_name"],
            "--version", manifest["package_version"], first.manifest_artifact_id, first.package_artifact_id)
        assert failed.returncode != 0 and envelope["error"]["code"] == "FAILED_PRECONDITION", envelope
        assert envelope["error"]["details"]["package_name"] == manifest["package_name"]
        assert envelope["error"]["details"]["package_version"] == manifest["package_version"]
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "UNINSTALLED"
        # The currently-serving ACTIVE installation cannot be uninstalled out
        # from under serving; only INSTALLED/INACTIVE installations qualify.
        failed, envelope = invoke(data_dir, "harness", "uninstall", new_id)
        assert failed.returncode != 0 and envelope["error"]["code"] == "FAILED_PRECONDITION", envelope
        assert envelope["error"]["details"]["status"] == "ACTIVE"
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "ACTIVE"
        assert admin(data_dir, "refs")["serving_revision"] == 2
        result, execution = asyncio.run(terminal_execution(data_dir, submit(data_dir, tmp_path, "normal")))
        assert_result(result, execution, version="0.1.1-dev.1")


def test_second_distinct_rollback_envelope_mints_a_fresh_generation_without_resurrection(tmp_path):
    """Idempotency belongs to the exact envelope bytes; a newly approved
    activation of the same package is a fresh grant generation, not a replay."""
    from agent_meta_runtime.sdk import connect
    first, publisher = version_bundle(1)
    second, _ = version_bundle(2)
    method = "agent_meta.public.v1.Harness.Activate"
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        old_id = install_seed(data_dir, tmp_path, first, activate=False)
        original = activate_seed(data_dir, first, old_id)
        asyncio.run(wait_ready(data_dir, revision=1))
        served = submit(data_dir, tmp_path, "normal")
        served_result, served_execution = asyncio.run(terminal_execution(data_dir, served))
        assert_result(served_result, served_execution, version="0.1.0-dev.1")
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        activate_seed(data_dir, second, new_id)
        asyncio.run(wait_ready(data_dir, revision=2))
        rollback = activate_seed(data_dir, first, old_id)
        asyncio.run(wait_ready(data_dir, revision=3))
        distinct = prepared_activation(data_dir, first, old_id)
        async def reactivated():
            client = await connect(data_dir)
            try:
                first_resource = (await client.execute_command(method, distinct)).resource
                # The same distinct envelope replays its own durable receipt.
                replay_resource = (await client.execute_command(method, distinct)).resource
                assert replay_resource == first_resource
                assert first_resource["revision"] == 4
                assert set(first_resource["grant_ids"]).isdisjoint(original["grant_ids"])
                assert set(first_resource["grant_ids"]).isdisjoint(rollback["grant_ids"])
                assert first_resource["composition_id"] != rollback["composition_id"]
                return first_resource
            finally:
                await client.aclose()
        resource = asyncio.run(reactivated())
        asyncio.run(wait_ready(data_dir, revision=4))
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "ACTIVE"
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "INACTIVE"
        assert admin(data_dir, "harness", "inspect", old_id)["manifest_artifact_id"] == first.manifest_artifact_id
        # Confirmed work keeps its exact receipts; new Tasks still serve the
        # same old version under the newest composition.
        preserved = asyncio.run(terminal_execution(data_dir, served))
        assert preserved[0]["result_artifact_id"] == served_result["result_artifact_id"]
        result, execution = asyncio.run(terminal_execution(data_dir, submit(data_dir, tmp_path, "normal")))
        assert_result(result, execution, version="0.1.0-dev.1", composition_id=resource["composition_id"])
        assert execution["serving_revision"] == 4


def test_same_identity_conflicting_descriptor_revision_cannot_replace_in_place(tmp_path):
    """禁止原地替换包: a valid signed bundle with the same name/version but a
    different descriptor revision is a different hash and cannot be installed
    over the existing installation identity."""
    conflicting, _ = version_bundle(1, descriptor_revision=2)
    first, publisher = version_bundle(1)
    assert conflicting.manifest_artifact_id != first.manifest_artifact_id
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        # The conflicting bundle is a fully valid signed package on its own.
        for reference, raw in conflicting.artifacts.items():
            path = tmp_path / "conflicting.blob"
            path.write_bytes(raw)
            assert admin(data_dir, "artifact", "put", str(path), "--kind", "code")["artifact_id"] == reference
        assert admin(data_dir, "harness", "validate", conflicting.manifest_artifact_id)["valid"]
        install_seed(data_dir, tmp_path, first)
        asyncio.run(wait_ready(data_dir, revision=1))
        manifest = json.loads(conflicting.artifacts[conflicting.manifest_artifact_id])
        failed, envelope = invoke(data_dir, "harness", "install", "--name", manifest["package_name"],
            "--version", manifest["package_version"], conflicting.manifest_artifact_id, conflicting.package_artifact_id)
        assert failed.returncode != 0 and envelope["error"]["code"] == "IDEMPOTENCY_CONFLICT", envelope
        assert envelope["error"]["details"]["package_name"] == manifest["package_name"]
        assert envelope["error"]["details"]["package_version"] == manifest["package_version"]
        assert admin(data_dir, "refs")["serving_revision"] == 1
        result, execution = asyncio.run(terminal_execution(data_dir, submit(data_dir, tmp_path, "normal")))
        assert_result(result, execution, version="0.1.0-dev.1")


def test_superseded_activation_envelope_conflicts_and_winner_replays_idempotently(tmp_path):
    """Two envelopes prepared from the same base revision: exactly one wins,
    the loser conflicts, and the winner's receipt replays unchanged."""
    from agent_meta_runtime.sdk import ErrorCode, StableError
    first, publisher = version_bundle(1)
    second, _ = version_bundle(2)
    method = "agent_meta.public.v1.Harness.Activate"
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        old_id = install_seed(data_dir, tmp_path, first, activate=False)
        activate_seed(data_dir, first, old_id)
        asyncio.run(wait_ready(data_dir, revision=1))
        new_id = install_seed(data_dir, tmp_path, second, activate=False)
        winner = prepared_activation(data_dir, second, new_id)
        loser = prepared_activation(data_dir, second, new_id)
        async def race():
            client = await connect(data_dir)
            try:
                resource = (await client.execute_command(method, winner)).resource
                with pytest.raises(StableError) as error:
                    await client.execute_command(method, loser)
                assert error.value.code == ErrorCode.REVISION_CONFLICT, error.value
                receipt = (await client.execute_command(method, winner)).resource
                assert receipt == resource
                return resource
            finally:
                await client.aclose()
        resource = asyncio.run(race())
        asyncio.run(wait_ready(data_dir, revision=2))
        assert resource["revision"] == 2
        assert admin(data_dir, "harness", "inspect", new_id)["status"] == "ACTIVE"
        assert admin(data_dir, "harness", "inspect", old_id)["status"] == "INACTIVE"
        result, execution = asyncio.run(terminal_execution(data_dir, submit(data_dir, tmp_path, "normal")))
        assert_result(result, execution, version="0.1.1-dev.1", composition_id=resource["composition_id"])


def test_impossible_grant_requests_are_refused_before_installation(tmp_path):
    """A grant request that can never be exercised (zero uses) fails package
    admission at validation, before any activation or serving impact."""
    first, publisher = version_bundle(1)
    impossible = limit_activation_grant(first, permission="capability.invoke", max_uses=0)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        for reference, raw in impossible.artifacts.items():
            path = tmp_path / "impossible.blob"
            path.write_bytes(raw)
            assert admin(data_dir, "artifact", "put", str(path), "--kind", "code")["artifact_id"] == reference
        report = admin(data_dir, "harness", "validate", impossible.manifest_artifact_id)
        assert report["valid"] is False, report
        assert any(issue.startswith("grant_requests.invalid") for issue in report["issues"]), report
        manifest = json.loads(impossible.artifacts[impossible.manifest_artifact_id])
        failed, envelope = invoke(data_dir, "harness", "install", "--name", manifest["package_name"],
            "--version", manifest["package_version"], impossible.manifest_artifact_id, impossible.package_artifact_id)
        assert failed.returncode != 0 and envelope["error"]["code"] == "FAILED_PRECONDITION", envelope
        assert envelope["error"]["message"] == "package validation failed"
        # Serving is untouched and the healthy package still installs.
        assert admin(data_dir, "refs")["serving_revision"] == 0
        install_seed(data_dir, tmp_path, first)
        asyncio.run(wait_ready(data_dir, revision=1))
        result, execution = asyncio.run(terminal_execution(data_dir, submit(data_dir, tmp_path, "normal")))
        assert_result(result, execution, version="0.1.0-dev.1")
