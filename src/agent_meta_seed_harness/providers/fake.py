"""Explicit offline Provider for deterministic conformance workloads.

Scenarios are structured test inputs. Free model text is never interpreted as
commands; only normalized ToolCallPart values can reach Host dispatch.
"""

import json
import asyncio

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.host import JsonPart, ModelResponse, ProviderUsage, TextPart, ToolCallPart
from agent_meta_runtime.sdk.packages import canonical_json
from agent_meta_runtime.sdk.context import rendered_sections


async def invoke_fake(request):
    try:
        value = json.loads(rendered_sections(request.projection)["task_input"])
        if not isinstance(value, dict) or set(value) - {"provider", "scenario", "value"} or value.get("provider") != "fake":
            raise ValueError("explicit fake Provider selection required")
        scenario = value.get("scenario", "terminal")
        if scenario not in {"terminal", "echo", "two_echo", "free_text", "length", "wait", "invalid_arguments", "unknown_tool", "duplicate_calls"}:
            raise ValueError("unknown fake Provider scenario")
        payload = value.get("value", "hello")
        if not isinstance(payload, str) or len(payload.encode("utf-8")) > 4096:
            raise ValueError("bounded text value required")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise StableError(code=ErrorCode.INVALID_ARGUMENT, message="invalid offline Provider input") from exc
    usage = ProviderUsage(None, None, 0)
    if scenario == "wait":
        # Explicit offline workload for cancellation/owner-loss conformance.
        await asyncio.Event().wait()
    if scenario in {"invalid_arguments", "unknown_tool", "duplicate_calls"}:
        call = ToolCallPart("negative-1", "seed.missing" if scenario == "unknown_tool" else "seed.echo",
            canonical_json({"value": 7 if scenario == "invalid_arguments" else payload}).decode())
        return ModelResponse((call, call) if scenario == "duplicate_calls" else (call,), "TOOL_CALL", usage)
    if scenario in ("echo", "two_echo"):
        if request.ordinal == 0:
            count = 2 if scenario == "two_echo" else 1
            calls = tuple(ToolCallPart(f"echo-{index}", "seed.echo", canonical_json({"value": payload + (str(index) if count == 2 else "")}).decode()) for index in range(count))
            return ModelResponse((TextPart("running declared echo"), *calls), "TOOL_CALL", usage)
        history = json.loads(request.history_content)
        results = [json.loads(bytes.fromhex(item["content_hex"])) for item in history if item.get("role") == "tool" and item.get("error_code") is None]
        return ModelResponse((TextPart("echo complete"), JsonPart({"results": results}), TextPart("done")), "STOP", usage)
    if scenario == "free_text":
        return ModelResponse((TextPart('seed.echo({"value":"must not execute"})'),), "STOP", usage)
    return ModelResponse((TextPart(payload), JsonPart({"provider": "fake"}), TextPart("done")), "LENGTH" if scenario == "length" else "STOP", usage)
