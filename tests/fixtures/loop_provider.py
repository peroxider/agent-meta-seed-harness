"""Scripted consumer Provider for real Host conformance, never a Runtime fake."""

import json

from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import (ArtifactPart, JsonPart, ModelResponse, ProviderUsage,
    TextPart, ToolCallPart, ToolResultPart)
from agent_meta_runtime.sdk.packages import canonical_json


async def invoke_fake(request):
    print(canonical_json({"seed_probe_call": "model", "task_id": request.task.task_id}).decode(), flush=True)
    value = json.loads(rendered_sections(request.projection)["task_input"])
    scenario = value["scenario"]
    usage = ProviderUsage(None, None, 0)
    if scenario == "text":
        return ModelResponse((TextPart(value["value"]),), "STOP", usage)
    if scenario == "parts":
        return ModelResponse((TextPart("first"), JsonPart({"answer": 42}), ArtifactPart(request.task.input_artifact_id), TextPart("last")), "STOP", usage)
    if scenario == "length":
        return ModelResponse((TextPart("cut"),), "LENGTH", usage)
    if scenario in ("empty", "error_finish", "tool_result", "unknown_usage"):
        parts = {"empty": (), "error_finish": (TextPart("error"),),
            "tool_result": (ToolResultPart("foreign", "OK"),), "unknown_usage": (TextPart("unknown cost"),)}[scenario]
        return ModelResponse(parts, "ERROR" if scenario == "error_finish" else "STOP", None if scenario == "unknown_usage" else usage)
    if scenario == "free_text":
        return ModelResponse((TextPart('seed.echo({"value":"do not run"}); rm -rf /'),), "STOP", usage)
    history = json.loads(request.history_content)
    if request.ordinal == 0:
        assert history == []
    if scenario in ("forever", "cross_turn_duplicate") or request.ordinal == 0:
        count = 16 if scenario == "tool_16" else 17 if scenario == "tool_17" else 2 if scenario in ("two_tools", "duplicate_same", "tool_error") else 1
        calls = []
        for index in range(count):
            payload = "__ERROR__" if scenario == "tool_error" and index == 0 else "__INVALID__" if scenario == "malformed_tool_result" else str(index)
            identity = "same" if scenario in ("cross_turn_duplicate", "duplicate_same") else f"{request.ordinal}-{index}"
            name = "seed.missing" if scenario == "unknown_tool" else "seed.echo"
            arguments = {"value": 7 if scenario == "bad_arguments" else payload}
            calls.append(ToolCallPart(identity, name, canonical_json(arguments).decode()))
        return ModelResponse((TextPart("assistant before tools"), *calls), "TOOL_CALL", usage)
    assert history[0]["role"] == "model"
    assert history[0]["response"]["parts"][0] == {"kind": "text", "text": "assistant before tools"}
    tools = [item for item in history if item["role"] == "tool"]
    results = []
    for index, item in enumerate(tools):
        assert item["call_id"] == f"0-{index}"
        if item["error_code"]:
            assert item["error_code"] == "INVALID_RESULT" and item["content_hex"] is None
            results.append({"error": item["error_code"]})
        else:
            decoded = json.loads(bytes.fromhex(item["content_hex"]))
            assert decoded == {"value": str(index)}
            results.append(decoded)
    return ModelResponse((TextPart("terminal"), JsonPart({"results": results}), TextPart("last")), "STOP", usage)
