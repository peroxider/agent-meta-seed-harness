"""Bounded terminal-only Messages codec. No network, credentials or retries.

This deliberately narrow wire profile is not proof of a gateway's behavior.
Both a future controlled transport and offline replay consume these bytes.
"""
from __future__ import annotations

import json
import re

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.host import (
    ModelResponse, ProviderUsage, TextPart, ToolCallPart, encode_model_response,
)
from agent_meta_runtime.sdk.packages import canonical_json

MAX_RESPONSE_BYTES = 1 << 20
WIRE_PROFILE = "anthropic-messages-terminal/v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,200}\Z")


def _invalid(reason):
    return StableError(code=ErrorCode.INVALID_RESULT,
        message="invalid Provider terminal response", details={"reason_code": reason})


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _bounded(value, depth=0, count=None):
    if count is None:
        count = [0]
    count[0] += 1
    if depth > 32 or count[0] > 16384:
        raise ValueError("JSON complexity exceeded")
    if isinstance(value, dict):
        for item in value.values():
            _bounded(item, depth + 1, count)
    elif isinstance(value, list):
        for item in value:
            _bounded(item, depth + 1, count)


def _tokens(value):
    if value is not None and (type(value) is not int or not 0 <= value <= 2**53 - 1):
        raise ValueError("invalid usage counter")
    return value


def normalize_terminal(raw: bytes, *, expected_model: str) -> ModelResponse:
    """Normalize one complete response; never infer calls from free text.

    Unknown usage/cost stays unknown. Cache accounting and reasoning/server
    tools need their own explicit profile; they are not silently discarded.
    Error diagnostics contain neither raw upstream content nor request data.
    """
    if not isinstance(expected_model, str) or not _IDENTIFIER.fullmatch(expected_model):
        raise StableError(code=ErrorCode.INVALID_ARGUMENT, message="explicit Provider model required")
    if type(raw) is not bytes or not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise _invalid("RESPONSE_SIZE")
    try:
        body = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        _bounded(body)
        canonical_json(body)
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise _invalid("RESPONSE_JSON") from None
    if not isinstance(body, dict):
        raise _invalid("RESPONSE_SCHEMA")
    required = {"id", "type", "role", "model", "content", "stop_reason"}
    if not required <= set(body) or set(body) - required - {"stop_sequence", "usage"}:
        raise _invalid("RESPONSE_SCHEMA")
    if body["type"] != "message" or body["role"] != "assistant" or body["model"] != expected_model:
        raise _invalid("RESPONSE_BINDING")
    if not isinstance(body["id"], str) or not _IDENTIFIER.fullmatch(body["id"]):
        raise _invalid("RESPONSE_ID")
    reasons = {"end_turn": "STOP", "stop_sequence": "STOP", "max_tokens": "LENGTH", "tool_use": "TOOL_CALL"}
    reason = body["stop_reason"]
    if not isinstance(reason, str) or reason not in reasons:
        raise _invalid("UNSUPPORTED_STOP_REASON")
    stop = body.get("stop_sequence")
    if (reason == "stop_sequence" and (not isinstance(stop, str) or not stop)) or (reason != "stop_sequence" and stop is not None):
        raise _invalid("STOP_SEQUENCE")
    content = body["content"]
    if not isinstance(content, list) or not 1 <= len(content) <= 128:
        raise _invalid("CONTENT_PARTS")
    parts = []
    for block in content:
        if not isinstance(block, dict):
            raise _invalid("CONTENT_SCHEMA")
        if set(block) == {"type", "text"} and block["type"] == "text" and isinstance(block["text"], str):
            parts.append(TextPart(block["text"]))
        elif set(block) == {"type", "id", "name", "input"} and block["type"] == "tool_use":
            if not all(isinstance(block[k], str) and _IDENTIFIER.fullmatch(block[k]) for k in ("id", "name")) or not isinstance(block["input"], dict):
                raise _invalid("TOOL_SCHEMA")
            parts.append(ToolCallPart(block["id"], block["name"], canonical_json(block["input"]).decode()))
        else:
            raise _invalid("UNSUPPORTED_CONTENT")
    has_tools = any(isinstance(p, ToolCallPart) for p in parts)
    if has_tools != (reason == "tool_use"):
        raise _invalid("INCOMPLETE_OR_CONTRADICTORY_TOOLS")
    usage = body.get("usage")
    input_tokens = output_tokens = None
    if usage is not None:
        if not isinstance(usage, dict) or set(usage) - {"input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"}:
            raise _invalid("UNSUPPORTED_USAGE")
        try:
            input_tokens, output_tokens = _tokens(usage.get("input_tokens")), _tokens(usage.get("output_tokens"))
            for name in ("cache_creation_input_tokens", "cache_read_input_tokens"):
                if name in usage and _tokens(usage[name]) != 0:
                    raise ValueError("cache accounting requires explicit profile")
        except ValueError:
            raise _invalid("USAGE_ACCOUNTING") from None
    result = ModelResponse(tuple(parts), reasons[reason], ProviderUsage(input_tokens, output_tokens, None))
    try:
        encode_model_response(result)  # same public Host semantics as replay
    except (ValueError, TypeError, StableError):
        raise _invalid("NORMALIZED_RESPONSE") from None
    return result


def normalized_terminal_bytes(raw: bytes, *, expected_model: str) -> bytes:
    """No raw headers, IDs, model routing or upstream metadata are persisted."""
    return encode_model_response(normalize_terminal(raw, expected_model=expected_model))
