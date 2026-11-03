"""Deterministic JSON normalization; no dynamic execution or external IO."""
import json

from agent_meta_runtime.sdk import ErrorCode
from agent_meta_runtime.sdk.host import InvocationResult
from agent_meta_runtime.sdk.packages import canonical_json


async def normalize_json(request):
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError('duplicate JSON field')
            result[name] = value
        return result
    try:
        arguments = json.loads(request.call.arguments_json, object_pairs_hook=unique)
        if not isinstance(arguments, dict) or set(arguments) != {'json'} or not isinstance(arguments['json'], str):
            raise ValueError('normalization arguments differ')
        if len(arguments['json'].encode('utf-8')) > 65536:
            raise ValueError('JSON input exceeds byte ceiling')
        value = json.loads(arguments['json'], object_pairs_hook=unique)
        raw = canonical_json({'value': value})
        if len(raw) > 1024 * 1024:
            raise ValueError('normalized JSON exceeds byte ceiling')
        return InvocationResult(content=raw)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return InvocationResult(error_code=ErrorCode.INVALID_ARGUMENT)
