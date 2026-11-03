"""SH-REC-01: durable model/tool history across real process loss."""

import asyncio

import pytest

from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, TextPart, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

from recovery_runtime import probe_events, terminal_execution, wait_invocations
from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import admin, daemon_process


PROVIDER = b'''
import json
from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import JsonPart, ModelResponse, ProviderUsage, TextPart, ToolCallPart
from agent_meta_runtime.sdk.packages import canonical_json

async def invoke_fake(request):
    print(canonical_json({"seed_probe_call": request.request_id, "kind": "model", "ordinal": request.ordinal}).decode(), flush=True)
    if request.ordinal == 0:
        unknown = json.loads(rendered_sections(request.projection)["task_input"])["scenario"] == "unknown"
        return ModelResponse((TextPart("before tool"), ToolCallPart("echo-0", "seed.echo", canonical_json({"value": "wait" if unknown else "done"}).decode())), "TOOL_CALL", ProviderUsage(None, None, 0))
    history = json.loads(request.history_content)
    assert [item["role"] for item in history] == ["model", "tool"]
    assert history[0]["response"]["parts"][0] == {"kind": "text", "text": "before tool"}
    assert history[1]["call_id"] == "echo-0" and history[1]["error_code"] is None
    assert json.loads(bytes.fromhex(history[1]["content_hex"])) == {"value": "done"}
    return ModelResponse((TextPart("after tool"), JsonPart({"value": "done"})), "STOP", ProviderUsage(None, None, 0))
'''

ECHO = b'''
import asyncio
import json
from agent_meta_runtime.sdk.host import InvocationResult
from agent_meta_runtime.sdk.packages import canonical_json

async def echo(request):
    print(canonical_json({"seed_probe_call": request.request_id, "kind": "tool"}).decode(), flush=True)
    value = json.loads(request.call.arguments_json)["value"]
    if value == "wait":
        await asyncio.Event().wait()
    return InvocationResult(content=canonical_json({"value": value}))
'''

LOOP = b'''
import asyncio
from agent_meta_runtime.sdk.host import ToolCallPart, terminal_result
from .context import project

async def run_task(task, host):
    response = await host.invoke_model(await project(task, host))
    calls = [part for part in response.parts if isinstance(part, ToolCallPart)]
    assert len(calls) == 1
    await host.invoke_tool(calls[0])
    await asyncio.sleep(3)
    return terminal_result(await host.invoke_model(await project(task, host)))
'''


@pytest.mark.parametrize("confirmed", [False, True])
@pytest.mark.parametrize("execution_backend", ["trusted_in_process", "in_memory"])
def test_confirmed_tool_replays_history_and_unknown_tool_stops_without_redispatch(tmp_path, confirmed, execution_backend):
    bundle, publisher = seed_bundle(overrides={"agent_meta_seed_harness/providers/fake.py": PROVIDER,
        "agent_meta_seed_harness/capabilities/echo.py": ECHO, "agent_meta_seed_harness/loop.py": LOOP})
    with daemon_process(tmp_path, publishers=[publisher], label="first", execution_backend=execution_backend) as first:
        install_seed(first.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(first.data_dir))
        path = tmp_path / "input.json"
        path.write_bytes(canonical_json({"provider": "fake", "scenario": "confirmed" if confirmed else "unknown", "value": "fixture"}))
        reference = admin(first.data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
        task_id = admin(first.data_dir, "task", "submit", "--input-artifact", reference)["task_id"]
        before = asyncio.run(wait_invocations(first.data_dir, task_id, statuses=["SUCCEEDED", "SUCCEEDED" if confirmed else "RUNNING"]))
        assert [item["kind"] for item in probe_events(first)] == ["model", "tool"]
        assert before["consumed_budget"]["steps"] == 2 and before["consumed_budget"]["model_calls"] == 1
        first.process.kill()
        first.process.wait(timeout=10)
    with daemon_process(tmp_path, publishers=[publisher], label="restarted", execution_backend=execution_backend) as restarted:
        asyncio.run(wait_ready(restarted.data_dir))
        result, after = asyncio.run(terminal_execution(restarted.data_dir, task_id))
        assert after["projections"] == before["projections"]
        assert [item["invocation_id"] for item in after["invocations"][:2]] == [item["invocation_id"] for item in before["invocations"]]
        if execution_backend == "in_memory":
            for old_i, new_i in zip(before["invocations"][:2 if confirmed else 1], after["invocations"]):
                old, new = old_i["execution_binding"], new_i["execution_binding"]
                assert old["ack_state"] in ("PENDING", "ACKNOWLEDGED")
                assert new["ack_state"] in ("PENDING", "ACKNOWLEDGED", "UNAVAILABLE_SESSION_LOST")
                if old["ack_state"] == "ACKNOWLEDGED":
                    assert new["ack_state"] == "ACKNOWLEDGED"
                old["ack_state"] = new["ack_state"]
        if confirmed:
            assert result["status"] == "SUCCEEDED" and after["invocations"][:2] == before["invocations"], result
            assert [item["kind"] for item in probe_events(restarted)] == ["model"]
            assert probe_events(restarted)[0]["ordinal"] == 1
            assert after["consumed_budget"] == {"turns": 2, "model_calls": 2, "steps": 3, "effects": 2, "cost_microunits": 0}
            expected = encode_terminal_result(TerminalResult((TextPart("after tool"), JsonPart({"value": "done"}))))
            assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(expected)
        else:
            assert result["status"] == "FAILED_RECOVERY" and result["error"] == "EXTERNAL_EFFECT_UNKNOWN", result
            assert probe_events(restarted) == [] and len(after["invocations"]) == 2
            assert after["invocations"][0] == before["invocations"][0]
            assert after["invocations"][1]["status"] == "FAILED"
            assert after["consumed_budget"]["steps"] == 2 and after["consumed_budget"]["model_calls"] == 1
            if execution_backend == "in_memory":
                assert after["invocations"][1]["execution_binding"]["terminal_status"] == "UNKNOWN"
