"""Explicit zero-cost typed tool workloads; free text is never dispatched."""
import json

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import (JsonPart, ModelResponse, ProviderUsage, TextPart, ToolCallPart,
    encode_model_response, encode_terminal_result, terminal_result)
from agent_meta_runtime.sdk.packages import canonical_json

MAX_RESULT_BYTES = 1024 * 1024
MAX_HISTORY_BYTES = 4 * MAX_RESULT_BYTES


def _history_results(history_content):
    if len(history_content) > MAX_HISTORY_BYTES:
        raise StableError(code=ErrorCode.RESOURCE_EXHAUSTED, message='offline tools history exceeds aggregate ceiling')
    results, total = [], 0
    try:
        history = json.loads(history_content)
        if not isinstance(history, list):
            raise ValueError('history must be ordered')
        for item in history:
            if not isinstance(item, dict):
                raise ValueError('history item must be normalized')
            if item.get('role') != 'tool' or item.get('error_code') is not None:
                continue
            encoded = item['content_hex']
            if not isinstance(encoded, str):
                raise ValueError('tool content must be immutable JSON bytes')
            # Check before decoding/parsing each result. Individual tools have
            # their own ceiling; their sum needs a separate one.
            total += (len(encoded) + 1) // 2
            if total > MAX_RESULT_BYTES:
                raise StableError(code=ErrorCode.RESOURCE_EXHAUSTED, message='offline tools results exceed aggregate ceiling')
            results.append(json.loads(bytes.fromhex(encoded)))
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise StableError(code=ErrorCode.INVALID_RESULT, message='invalid normalized offline tools history') from None
    return results


def _terminal_results(history_content):
    results = _history_results(history_content)
    response = ModelResponse((JsonPart({'results':results}),), 'STOP', ProviderUsage(None, None, 0))
    # Include all wrappers/escaping in both published representations. A body
    # just below the limit is not permission to exceed it during serialization.
    if max(len(encode_model_response(response)), len(encode_terminal_result(terminal_result(response)))) > MAX_RESULT_BYTES:
        raise StableError(code=ErrorCode.RESOURCE_EXHAUSTED, message='offline tools terminal exceeds the 1 MiB ceiling')
    return response


def _resolve(value, results, depth=0):
    if depth > 16:
        raise ValueError('recipe nesting exceeds ceiling')
    if type(value) is dict:
        if '$result' in value:
            reference = value['$result']
            if (set(value) != {'$result'} or type(reference) is not dict or set(reference) != {'index','path'}
                    or type(reference['index']) is not int or not 0 <= reference['index'] < len(results)
                    or type(reference['path']) is not list or not 1 <= len(reference['path']) <= 8):
                raise ValueError('invalid prior result reference')
            selected = results[reference['index']]
            for key in reference['path']:
                if type(selected) is dict and type(key) is str:
                    selected = selected[key]
                elif type(selected) is list and type(key) is int and 0 <= key < len(selected):
                    selected = selected[key]
                else:
                    raise ValueError('result path is unavailable')
            return selected
        return {key:_resolve(item, results, depth+1) for key,item in value.items()}
    if type(value) is list:
        return [_resolve(item, results, depth+1) for item in value]
    return value


async def invoke_fake_tools(request):
    try:
        value = json.loads(rendered_sections(request.projection)['task_input'])
        if not isinstance(value, dict) or set(value) - {'provider', 'scenario', 'calls'} or value.get('provider') != 'fake-tools':
            raise ValueError('explicit offline tools provider required')
        scenario = value.get('scenario', 'tools')
        if scenario not in ('tools', 'free_text', 'sequence') or not isinstance(value.get('calls'), list) or len(value['calls']) > 16:
            raise ValueError('unsupported bounded tool workload')
        calls = []
        for index, call in enumerate(value['calls']):
            if not isinstance(call, dict) or set(call) != {'name', 'arguments'} or not isinstance(call['name'], str) or not isinstance(call['arguments'], dict):
                raise ValueError('invalid normalized workload call')
            calls.append(ToolCallPart(f'tool-{index}', call['name'], canonical_json(call['arguments']).decode()))
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise StableError(code=ErrorCode.INVALID_ARGUMENT, message='invalid offline tools workload') from None
    usage = ProviderUsage(None, None, 0)
    if scenario == 'free_text':
        return ModelResponse((TextPart('seed.artifact.put({"value":"text is not a tool call"})'),), 'STOP', usage)
    if scenario == 'sequence':
        results = _history_results(request.history_content)
        if request.ordinal != len(results):
            raise StableError(code=ErrorCode.INVALID_RESULT, message='offline sequence has an unconfirmed prior call')
        if len(results) < len(calls):
            call = calls[len(results)]
            try:
                arguments = _resolve(json.loads(call.arguments_json), results)
            except (ValueError, KeyError, TypeError, RecursionError):
                raise StableError(code=ErrorCode.INVALID_ARGUMENT, message='invalid offline sequence result reference') from None
            return ModelResponse((ToolCallPart(call.call_id, call.name, canonical_json(arguments).decode()),), 'TOOL_CALL', usage)
        return _terminal_results(request.history_content)
    if request.ordinal == 0 and calls:
        return ModelResponse(tuple(calls), 'TOOL_CALL', usage)
    return _terminal_results(request.history_content)
