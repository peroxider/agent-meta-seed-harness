"""PURE echo over the declared normalized operation schema."""

import json

from agent_meta_runtime.sdk.host import InvocationResult
from agent_meta_runtime.sdk.packages import canonical_json


async def echo(request):
    arguments = json.loads(request.call.arguments_json)
    return InvocationResult(content=canonical_json({"value": arguments["value"]}))
