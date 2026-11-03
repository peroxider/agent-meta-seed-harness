"""Synthetic Messages wire data, never captured upstream R2 evidence."""
from agent_meta_runtime.sdk.packages import canonical_json

MODEL = "glm-5.3-flash"


def response(**changes):
    body = {"id": "msg_fixture", "type": "message", "role": "assistant", "model": MODEL,
        "content": [{"type": "text", "text": "hello"}], "stop_reason": "end_turn", "stop_sequence": None}
    return {**body, **changes}


def wire(**changes):
    return canonical_json(response(**changes))


def tool(index=0):
    return {"type": "tool_use", "id": f"call_{index}", "name": "seed.echo", "input": {"value": str(index)}}
