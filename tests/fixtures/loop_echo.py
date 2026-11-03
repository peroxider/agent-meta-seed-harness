"""Consumer-owned PURE tool, including declared failure/result fixtures."""

import json

from agent_meta_runtime.sdk.host import InvocationResult
from agent_meta_runtime.sdk.packages import canonical_json


async def echo(request):
    print(canonical_json({"seed_probe_call": "tool", "task_id": request.task.task_id}).decode(), flush=True)
    value = json.loads(request.call.arguments_json)["value"]
    if value == "__ERROR__":
        return InvocationResult(error_code="INVALID_RESULT")
    if value == "__INVALID__":
        return InvocationResult(content=b'"invalid object result"')
    return InvocationResult(content=canonical_json({"value": value}))
