"""SH-LOOP-01: actual signed Seed Loop and normalized Provider/Host outcomes."""

import asyncio

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.host import ArtifactPart, JsonPart, ModelResponse, ProviderUsage, TerminalResult, TextPart, ToolCallPart, decode_model_response, encode_model_response, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex, validate_loop_policy

from seed_runtime import admin
from loop_runtime import loop_runtime, run_workload


@pytest.mark.parametrize("scenario", ["parts", "length", "free_text"])
def test_complete_terminal_parts_are_preserved_and_text_never_dispatches(loop_runtime, scenario):
    result, invocations, input_ref = run_workload(loop_runtime, scenario)
    assert result["status"] == "SUCCEEDED" and len(invocations) == 1, result
    expected = {
        "parts": TerminalResult((TextPart("first"), JsonPart({"answer": 42}), ArtifactPart(input_ref), TextPart("last"))),
        "length": TerminalResult((TextPart("cut"),), True),
        "free_text": TerminalResult((TextPart('seed.echo({"value":"do not run"}); rm -rf /'),)),
    }[scenario]
    assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(encode_terminal_result(expected))


@pytest.mark.parametrize("scenario,code", [("empty", "INVALID_RESULT"), ("error_finish", "INVALID_RESULT"),
    ("tool_result", "INVALID_RESULT"), ("unknown_usage", "FEATURE_UNAVAILABLE")])
def test_invalid_model_response_cannot_form_terminal_or_tool_dispatch(loop_runtime, scenario, code):
    result, invocations, _ = run_workload(loop_runtime, scenario)
    assert result["status"] == "FAILED" and result["error"] == code and not result["result_artifact_id"], result
    assert len(invocations) == 1


def test_loop_policy_terminates_repeated_tool_requests_without_a_ninth_model_call(loop_runtime):
    result, invocations, _ = run_workload(loop_runtime, "forever")
    assert result["status"] == "FAILED" and result["error"] == "RESOURCE_EXHAUSTED", result
    assert len(invocations) == 16  # eight accepted model calls and eight PURE tools


@pytest.mark.parametrize("budget,expected", [({"max_turns": 0}, 0), ({"max_model_calls": 0}, 0),
    ({"max_turns": 1}, 2), ({"max_model_calls": 1}, 2), ({"max_steps": 1}, 1), ({"max_effects": 0}, 0)])
def test_task_ceiling_remains_stricter_than_seed_policy(loop_runtime, budget, expected):
    result, invocations, _ = run_workload(loop_runtime, "forever", budget=budget)
    assert result["status"] == "FAILED" and result["error"] == "RESOURCE_EXHAUSTED", result
    assert len(invocations) == expected


def test_default_loop_retains_no_raw_provider_response(loop_runtime):
    data_dir, root = loop_runtime
    path = root / "workload.json"
    path.write_bytes(canonical_json({"provider": "fake", "scenario": "two_tools", "value": "fixture"}))
    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
    task = admin(data_dir, "task", "submit", "--input-artifact", reference)
    async def observed():
        client = await connect(data_dir)
        try:
            result, terminal = await client.wait_task(task["task_id"], timeout_s=10)
            assert terminal and result["status"] == "SUCCEEDED", result
            execution = await client.get_task_execution(task["task_id"])
            trace = await client.get_task_trace(task["task_id"])
            stored = execution["projections"][0]
            manifest_id = "artifact://sha256/" + sha256_hex(canonical_json(stored["manifest"]))
            registered = {event["entity_id"] for event in trace["events"]
                if event["event_type"] == "artifact_registered" and event["entity_type"] == "artifact"}
            assert registered == {manifest_id}, sorted(registered)
            for invocation in execution["invocations"]:
                content = await client.get_artifact_content(invocation["output_artifact_id"])
                assert invocation["output_artifact_id"] == "artifact://sha256/" + sha256_hex(content)
                if invocation["kind"] == "MODEL":
                    assert content == encode_model_response(decode_model_response(content)), content[:200]
        finally:
            await client.aclose()
    asyncio.run(observed())


def test_loop_policy_schema_cannot_express_raw_retention():
    base = {"schema": "harness-loop-policy/v1", "max_turns": 1, "max_steps": 1,
        "max_model_calls": 1, "stop_on_tool_error": True}
    assert validate_loop_policy(base) == ()
    assert validate_loop_policy({**base, "raw_retention": "ALLOWED"}) == ("loop_policy.unknown_field:raw_retention",)
