"""Bounded serial Loop; Runtime retains independent hard enforcement."""

import json

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.host import ToolCallPart, terminal_result, validate_response
from agent_meta_runtime.sdk.packages import validate_loop_policy

from .context import project


async def run_task(task, host):
    policy = json.loads(task.loop_policy_content)
    if validate_loop_policy(policy):
        raise StableError(code=ErrorCode.CONTRACT_INCOMPATIBLE, message="unsupported Seed loop policy")
    turns = min(policy["max_turns"], policy["max_model_calls"], task.budget.max_turns, task.budget.max_model_calls)
    for _ in range(turns):
        host.check_cancelled()
        response = await host.invoke_model(await project(task, host))
        if validate_response(response):
            raise StableError(code=ErrorCode.INVALID_RESULT, message="invalid normalized Seed model response")
        calls = tuple(part for part in response.parts if isinstance(part, ToolCallPart))
        if not calls:
            return terminal_result(response)
        for call in calls:
            host.check_cancelled()
            result = await host.invoke_tool(call)
            if result.error_code and policy["stop_on_tool_error"]:
                raise StableError(code=result.error_code, message="tool failed under Seed loop policy")
    raise StableError(code=ErrorCode.RESOURCE_EXHAUSTED, message="Seed loop policy exhausted")
