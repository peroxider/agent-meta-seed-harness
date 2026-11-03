"""Deterministic conversion and malformed input rejection."""
import json
from types import SimpleNamespace

import pytest

from agent_meta_runtime.sdk.packages import canonical_json
from agent_meta_seed_harness.capabilities.transform import normalize_json


@pytest.mark.asyncio
@pytest.mark.parametrize('text,value', [(' {"z":2,"a":1} ', {'a':1,'z':2}), ('[true,null,1]', [True,None,1]), ('"text"','text')])
async def test_normalize_json_returns_stable_canonical_content(text, value):
    request = SimpleNamespace(call=SimpleNamespace(arguments_json=canonical_json({'json':text}).decode()))
    first = await normalize_json(request)
    assert first.error_code is None and first.content == canonical_json({'value':value})
    assert await normalize_json(request) == first


@pytest.mark.asyncio
@pytest.mark.parametrize('arguments', [{}, {'json':[]}, {'json':'{}','path':'forbidden'}, {'json':'{'},
    {'json':'{"v":1,"v":2}'}, {'json':'NaN'}, {'json':'Infinity'}, {'json':'1e999'},
    {'json':'9007199254740992'}, {'json':'"'+('x'*65536)+'"'}, {'json':'['*1000+'0'+']'*1000}])
async def test_normalize_json_has_no_dynamic_or_ambiguous_fallback(arguments):
    request = SimpleNamespace(call=SimpleNamespace(arguments_json=json.dumps(arguments)))
    result = await normalize_json(request)
    assert result.error_code == 'INVALID_ARGUMENT' and result.content is None
