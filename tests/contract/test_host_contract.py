"""SH-HOST-01: independent signed adapter over the actual public Host."""

import asyncio
import time

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, TextPart, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

from recovery_runtime import terminal_execution, wait_invocations
from seed_package import install_seed, limit_activation_grant, seed_bundle, wait_ready
from seed_runtime import admin, invoke, running_daemon


LOOP = b'''
import asyncio
from dataclasses import FrozenInstanceError, replace
import json
from agent_meta_runtime.sdk.host import TerminalResult, TextPart, ToolCallPart, terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from .context import project

saved_projection = None

async def run_task(task, host):
    global saved_projection
    assert not any(hasattr(host, key) for key in ("conn", "_store", "repository", "authority", "credential", "provider", "backend", "__dict__"))
    assert sha256_hex(task.input_content) == task.input_artifact_id.rsplit("/", 1)[1]
    assert sha256_hex(task.capability_surface_content) == task.capability_surface_artifact_id.rsplit("/", 1)[1]
    assert sha256_hex(task.acceptance_view_content) == task.acceptance_view_artifact_id.rsplit("/", 1)[1]
    view = json.loads(task.acceptance_view_content)
    assert view["composition_id"] == task.serving_composition_id
    assert view["meta_revision"] == task.accepted_meta_revision
    assert view["composition"] == json.loads(task.composition_content)
    assert tuple(sorted(view["state_snapshot"].items())) == task.state_snapshot
    assert isinstance(task.context.artifacts, tuple) and isinstance(task.context.sources, tuple)
    assert all(isinstance(raw, bytes) for _, raw in task.context.artifacts)
    try:
        task.serving_revision = 999
        raise AssertionError("Task snapshot was mutable")
    except FrozenInstanceError:
        pass
    scenario = json.loads(task.input_content)["scenario"]
    if scenario == "tool_first":
        await host.invoke_tool(ToolCallPart("invented", "seed.echo", '{"value":"x"}'))
    projection = await project(task, host)
    if scenario == "projection_clone":
        projection = replace(projection)
    if scenario == "foreign_projection":
        assert saved_projection is not None
        projection = saved_projection
    response = await host.invoke_model(projection)
    if scenario == "confirmed_cancel":
        await asyncio.sleep(3)
    calls = [part for part in response.parts if isinstance(part, ToolCallPart)]
    if scenario == "snapshot":
        saved_projection = projection
    elif scenario == "forged_terminal":
        return TerminalResult((TextPart("invented terminal"),))
    elif scenario == "early_terminal":
        return TerminalResult((TextPart("pending tools"),))
    elif scenario == "model_before_tools":
        await host.invoke_model(projection)
    elif scenario == "out_of_order":
        await host.invoke_tool(calls[1])
    elif scenario == "counterfeit_tool":
        await host.invoke_tool(replace(calls[0], arguments_json='{"value":"altered"}'))
    elif scenario == "repeated_tool":
        await host.invoke_tool(calls[0])
        await host.invoke_tool(calls[0])
    elif scenario == "tool_grant_limit":
        for call in calls:
            await host.invoke_tool(call)
    return terminal_result(response)
'''

PROVIDER = b'''
import asyncio
import json
from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import JsonPart, ModelResponse, ProviderUsage, TextPart, ToolCallPart

async def invoke_fake(request):
    scenario = json.loads(rendered_sections(request.projection)["task_input"])["scenario"]
    if scenario == "wait":
        await asyncio.Event().wait()
    if scenario in ("early_terminal", "model_before_tools", "out_of_order", "counterfeit_tool", "repeated_tool", "tool_grant_limit"):
        return ModelResponse((ToolCallPart("a", "seed.echo", '{"value":"first"}'),
            ToolCallPart("b", "seed.echo", '{"value":"second"}')), "TOOL_CALL", ProviderUsage(None, None, 0))
    return ModelResponse((TextPart("first"), JsonPart({"snapshot": "frozen"}), TextPart("last")), "STOP", ProviderUsage(None, None, 0))
'''

BINDING = b'''
from agent_meta_runtime.sdk.host import HarnessAdapter, HealthProbeInvocation, HealthStatus
from .loop import run_task
from .providers.fake import invoke_fake
from .capabilities.echo import echo

async def probe(request):
    assert isinstance(request, HealthProbeInvocation)
    assert not any(hasattr(request, name) for name in ("task", "task_id", "conn", "authority"))
    return HealthStatus("READY", "TASK_FREE_PROBE")

def create():
    return HarnessAdapter(run_task, invoke_fake, {"seed.echo": echo}, probe)
'''


@pytest.fixture(scope="module")
def host_runtime(tmp_path_factory):
    root = tmp_path_factory.mktemp("host-contract")
    bundle, publisher = seed_bundle(overrides={"agent_meta_seed_harness/loop.py": LOOP,
        "agent_meta_seed_harness/providers/fake.py": PROVIDER, "agent_meta_seed_harness/host_binding.py": BINDING})
    with running_daemon(root, publishers=[publisher]) as data_dir:
        install_seed(data_dir, root, bundle)
        asyncio.run(wait_ready(data_dir))
        yield data_dir, root


def submit_workload(runtime, scenario, *, deadline_at_us=None):
    data_dir, root = runtime
    path = root / "input.json"
    path.write_bytes(canonical_json({"provider": "fake", "scenario": scenario, "value": "fixture"}))
    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
    options = ["--deadline-at-us", str(deadline_at_us)] if deadline_at_us is not None else []
    return admin(data_dir, "task", "submit", "--input-artifact", reference, *options)["task_id"]


def workload(runtime, scenario):
    return asyncio.run(terminal_execution(runtime[0], submit_workload(runtime, scenario)))


def test_task_free_health_and_frozen_task_view_surface_context_reach_actual_model(host_runtime):
    result, execution = workload(host_runtime, "snapshot")
    assert result["status"] == "SUCCEEDED" and len(execution["invocations"]) == 1, result
    expected = TerminalResult((TextPart("first"), JsonPart({"snapshot": "frozen"}), TextPart("last")))
    assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(encode_terminal_result(expected))


@pytest.mark.parametrize("scenario,count", [("tool_first", 0), ("projection_clone", 0), ("forged_terminal", 1),
    ("early_terminal", 1), ("model_before_tools", 1), ("out_of_order", 1), ("counterfeit_tool", 1), ("repeated_tool", 2)])
def test_host_rejects_unissued_calls_or_terminal_without_extra_dispatch(host_runtime, scenario, count):
    result, execution = workload(host_runtime, scenario)
    assert result["status"] == "FAILED" and result["error"] == "INVALID_RESULT", result
    assert len(execution["invocations"]) == count
    assert not result["result_artifact_id"]


def test_context_projection_issued_to_another_task_cannot_be_reused(host_runtime):
    result, _ = workload(host_runtime, "snapshot")
    assert result["status"] == "SUCCEEDED"
    result, execution = workload(host_runtime, "foreign_projection")
    assert result["status"] == "FAILED" and result["error"] == "INVALID_RESULT", result
    assert execution["invocations"] == []


@pytest.mark.parametrize("permission", ["model.invoke", "capability.invoke"])
def test_exhausted_installation_grant_cannot_borrow_operator_or_bootstrap_authority(tmp_path, permission):
    bundle, publisher = seed_bundle(overrides={"agent_meta_seed_harness/loop.py": LOOP,
        "agent_meta_seed_harness/providers/fake.py": PROVIDER, "agent_meta_seed_harness/host_binding.py": BINDING})
    bundle = limit_activation_grant(bundle, permission=permission, max_uses=1)
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        install_seed(data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(data_dir))
        if permission == "model.invoke":
            first, first_execution = workload((data_dir, tmp_path), "snapshot")
            assert first["status"] == "SUCCEEDED" and first_execution["consumed_budget"]["model_calls"] == 1
            result, execution = workload((data_dir, tmp_path), "snapshot")
            assert execution["invocations"] == [] and execution["consumed_budget"] == {}
        else:
            result, execution = workload((data_dir, tmp_path), "tool_grant_limit")
            assert len(execution["invocations"]) == execution["consumed_budget"]["steps"] == 2
            assert execution["consumed_budget"]["model_calls"] == 1
        assert result["status"] == "FAILED" and result["error"] == "AUTHORITY_DENIED", result


@pytest.mark.parametrize("deadline", [0, 1])
def test_already_expired_task_never_dispatches_model_or_projection(host_runtime, deadline):
    task_id = submit_workload(host_runtime, "snapshot", deadline_at_us=deadline)
    result, execution = asyncio.run(terminal_execution(host_runtime[0], task_id))
    assert result["status"] == "TIMED_OUT" and result["error"] == "DEADLINE_EXCEEDED", result
    assert execution["deadline_at_us"] == deadline and execution["started_at_us"] is None
    assert execution["invocations"] == execution["projections"] == [] and execution["consumed_budget"] == {}


def test_running_model_deadline_propagates_and_keeps_reserved_counts(host_runtime):
    task_id = submit_workload(host_runtime, "wait", deadline_at_us=time.time_ns() // 1000 + 5_000_000)
    before = asyncio.run(wait_invocations(host_runtime[0], task_id, statuses=["RUNNING"]))
    result, after = asyncio.run(terminal_execution(host_runtime[0], task_id))
    assert result["status"] == "TIMED_OUT" and result["error"] == "EXTERNAL_EFFECT_UNKNOWN", result
    assert after["consumed_budget"] == before["consumed_budget"]
    assert after["consumed_budget"]["model_calls"] == after["consumed_budget"]["steps"] == 1
    assert after["invocations"][0]["invocation_id"] == before["invocations"][0]["invocation_id"]
    assert after["invocations"][0]["status"] == "FAILED"


@pytest.mark.parametrize("confirmed", [False, True])
def test_cancel_propagates_without_releasing_counts_or_rewriting_confirmed_output(host_runtime, confirmed):
    data_dir, _ = host_runtime
    task_id = submit_workload(host_runtime, "confirmed_cancel" if confirmed else "wait")
    before = asyncio.run(wait_invocations(data_dir, task_id, statuses=["SUCCEEDED" if confirmed else "RUNNING"]))
    admin(data_dir, "task", "cancel", task_id)
    result, after = asyncio.run(terminal_execution(data_dir, task_id))
    assert result["status"] == "CANCELLED", result
    assert after["consumed_budget"] == before["consumed_budget"]
    assert len(after["invocations"]) == 1
    if confirmed:
        assert after["invocations"] == before["invocations"]
    else:
        assert result["error"] == "EXTERNAL_EFFECT_UNKNOWN" and after["invocations"][0]["status"] == "FAILED"
    process, refused = invoke(data_dir, "task", "cancel", task_id)
    assert process.returncode == 6 and not refused["ok"] and refused["error"]["code"] == "FAILED_PRECONDITION", refused
    repeated, stable = asyncio.run(terminal_execution(data_dir, task_id))
    assert repeated == result and stable["invocations"] == after["invocations"] and stable["consumed_budget"] == after["consumed_budget"]


@pytest.mark.parametrize("budget", [False, 0, [], None, {"max_steps": True}])
def test_cli_rejects_invalid_budget_instead_of_widening_it(host_runtime, budget):
    data_dir, root = host_runtime
    path = root / "invalid-budget-input.json"
    path.write_bytes(canonical_json({"provider": "fake", "scenario": "snapshot", "value": "fixture"}))
    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
    process, result = invoke(data_dir, "task", "submit", "--input-artifact", reference, "--budget", canonical_json(budget).decode())
    assert process.returncode == 2 and not result["ok"] and result["error"]["code"] == "INVALID_ARGUMENT", result


@pytest.mark.parametrize("raw", ["", "{", '{"max_steps":1,"max_steps":2}'])
def test_cli_budget_json_errors_have_stable_parameter_result(host_runtime, raw):
    data_dir, root = host_runtime
    path = root / "invalid-json-input.json"
    path.write_bytes(canonical_json({"provider": "fake", "scenario": "snapshot", "value": "fixture"}))
    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
    process, result = invoke(data_dir, "task", "submit", "--input-artifact", reference, "--budget", raw)
    assert process.returncode == 2 and not result["ok"] and result["error"]["code"] == "INVALID_ARGUMENT", result
