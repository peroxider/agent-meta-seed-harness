"""Aggregate result limits are distinct from each tool's content ceiling."""
from types import SimpleNamespace
import json

import pytest

from agent_meta_runtime.sdk import StableError
from agent_meta_runtime.sdk.host import encode_model_response, encode_terminal_result, terminal_result
from agent_meta_runtime.sdk.packages import canonical_json
from agent_meta_seed_harness.providers import fake_tools


def history(*values):
    return canonical_json([{'role':'tool','call_id':str(index),'error_code':None,
        'content_hex':canonical_json(value).hex()} for index, value in enumerate(values)])


@pytest.fixture
def model_request(monkeypatch):
    monkeypatch.setattr(fake_tools, 'rendered_sections', lambda _: {'task_input':'{"provider":"fake-tools","calls":[]}'})
    return SimpleNamespace(ordinal=1, projection=None, history_content=b'[]')


@pytest.mark.asyncio
async def test_terminal_keeps_bounded_results_without_loss_or_truncation(model_request):
    value = {'text':'多语言文本', 'items':[True,None,42]}
    model_request.history_content = history(value)
    response = await fake_tools.invoke_fake_tools(model_request)
    assert json.loads(encode_model_response(response))['parts'][0]['value'] == {'results':[value]}
    assert max(len(encode_model_response(response)), len(encode_terminal_result(terminal_result(response)))) <= fake_tools.MAX_RESULT_BYTES


@pytest.mark.asyncio
async def test_multiple_legal_results_cannot_bypass_the_aggregate_ceiling(model_request):
    model_request.history_content = history({'blob':'x'*600000}, {'blob':'y'*600000})
    with pytest.raises(StableError) as denied:
        await fake_tools.invoke_fake_tools(model_request)
    assert denied.value.code == 'RESOURCE_EXHAUSTED'


@pytest.mark.asyncio
async def test_published_encoding_overhead_counts_toward_the_terminal_ceiling(model_request):
    value = {'blob':'x'*(fake_tools.MAX_RESULT_BYTES-40)}
    assert len(canonical_json(value)) < fake_tools.MAX_RESULT_BYTES
    model_request.history_content = history(value)
    with pytest.raises(StableError) as denied:
        await fake_tools.invoke_fake_tools(model_request)
    assert denied.value.code == 'RESOURCE_EXHAUSTED'


@pytest.mark.asyncio
async def test_oversized_history_is_refused_before_parsing(model_request):
    model_request.history_content = b'not JSON' + b' ' * fake_tools.MAX_HISTORY_BYTES
    with pytest.raises(StableError) as denied:
        await fake_tools.invoke_fake_tools(model_request)
    assert denied.value.code == 'RESOURCE_EXHAUSTED'


@pytest.mark.asyncio
@pytest.mark.parametrize('content', [b'{}', b'[{"role":"tool","content_hex":"zz"}]', b'[{"role":"tool","content_hex":null}]'])
async def test_malformed_history_never_becomes_an_empty_success(model_request, content):
    model_request.history_content = content
    with pytest.raises(StableError) as denied:
        await fake_tools.invoke_fake_tools(model_request)
    assert denied.value.code == 'INVALID_RESULT'
