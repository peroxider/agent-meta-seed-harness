"""SH-TOOL-01: serial typed calls, full history, schema and global call IDs."""

import asyncio

import pytest

from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, TextPart, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

from recovery_runtime import terminal_execution
from loop_runtime import loop_runtime, run_workload, scripted_bundle
from seed_package import install_seed, limit_activation_grant, wait_ready
from seed_runtime import admin, running_daemon


@pytest.mark.parametrize("scenario,count", [("two_tools", 2), ("tool_16", 16)])
def test_tools_run_in_response_order_with_complete_assistant_history(loop_runtime, scenario, count):
    result, invocations, _ = run_workload(loop_runtime, scenario)
    assert result["status"] == "SUCCEEDED" and len(invocations) == count + 2, result
    expected = TerminalResult((TextPart("terminal"), JsonPart({"results": [{"value": str(i)} for i in range(count)]}), TextPart("last")))
    assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(encode_terminal_result(expected))


@pytest.mark.parametrize("scenario,code,count", [("tool_17", "INVALID_RESULT", 1), ("duplicate_same", "INVALID_RESULT", 1),
    ("cross_turn_duplicate", "INVALID_RESULT", 3), ("unknown_tool", "AUTHORITY_DENIED", 1),
    ("bad_arguments", "INVALID_RESULT", 1), ("malformed_tool_result", "INVALID_RESULT", 2), ("tool_error", "INVALID_RESULT", 2)])
def test_invalid_tool_paths_cannot_dispatch_another_call(loop_runtime, scenario, code, count):
    result, invocations, _ = run_workload(loop_runtime, scenario)
    assert result["status"] == "FAILED" and result["error"] == code, result
    assert len(invocations) == count


@pytest.mark.parametrize("execution_backend", ["trusted_in_process", "in_memory"])
def test_continue_on_tool_error_is_explicit_and_preserves_ordered_error_history(tmp_path, execution_backend):
    policy = {"schema": "harness-loop-policy/v1", "max_turns": 8, "max_steps": 40, "max_model_calls": 8, "stop_on_tool_error": False}
    bundle, publisher = scripted_bundle(loop_policy=policy)
    with running_daemon(tmp_path, publishers=[publisher], execution_backend=execution_backend) as data_dir:
        install_seed(data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(data_dir))
        result, invocations, _ = run_workload((data_dir, tmp_path), "tool_error")
        assert result["status"] == "SUCCEEDED" and len(invocations) == 4, result
        expected = TerminalResult((TextPart("terminal"), JsonPart({"results": [{"error": "INVALID_RESULT"}, {"value": "1"}]}), TextPart("last")))
        assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(encode_terminal_result(expected))


def test_inmemory_schema_failure_stops_even_when_declared_tool_errors_can_continue(tmp_path):
    policy = {"schema": "harness-loop-policy/v1", "max_turns": 8, "max_steps": 40, "max_model_calls": 8, "stop_on_tool_error": False}
    bundle, publisher = scripted_bundle(loop_policy=policy)
    with running_daemon(tmp_path, publishers=[publisher], execution_backend="in_memory") as data_dir:
        install_seed(data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(data_dir))
        result, invocations, _ = run_workload((data_dir, tmp_path), "malformed_tool_result")
        assert result["status"] == "FAILED" and result["error"] == "INVALID_RESULT", result
        assert len(invocations) == 2


@pytest.mark.parametrize("execution_backend", ["trusted_in_process", "in_memory"])
def test_continued_tool_error_still_enforces_next_tool_authority(tmp_path, execution_backend):
    policy = {"schema": "harness-loop-policy/v1", "max_turns": 8, "max_steps": 40, "max_model_calls": 8, "stop_on_tool_error": False}
    bundle, publisher = scripted_bundle(loop_policy=policy)
    bundle = limit_activation_grant(bundle, permission="capability.invoke", max_uses=1)
    with running_daemon(tmp_path, publishers=[publisher], execution_backend=execution_backend) as data_dir:
        install_seed(data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(data_dir))
        path = tmp_path / "tool-error.json"
        path.write_bytes(canonical_json({"provider": "fake", "scenario": "tool_error", "value": "fixture"}))
        reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
        task_id = admin(data_dir, "task", "submit", "--input-artifact", reference)["task_id"]
        result, execution = asyncio.run(terminal_execution(data_dir, task_id))
        assert result["status"] == "FAILED" and result["error"] == "AUTHORITY_DENIED", result
        assert len(execution["invocations"]) == execution["consumed_budget"]["steps"] == 2
        assert execution["consumed_budget"]["model_calls"] == 1
        assert [item["kind"] for item in execution["invocations"]] == ["MODEL", "CAPABILITY"]
        assert execution["invocations"][1]["status"] == "FAILED" and execution["invocations"][1]["error"] == "INVALID_RESULT"
