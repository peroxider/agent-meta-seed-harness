"""Public-only deterministic plans and strict serial normalized history."""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.context import SECTION_DELIMITER,SECTION_IDS
from agent_meta_runtime.sdk.host import (ContextProjection,ModelInvocation,ModelResponse,ProjectionManifest,
    ProviderTerminalResponse,Section,SourceRef,TextPart,ToolCallPart,encode_model_response)
from agent_meta_runtime.sdk.packages import canonical_json,sha256_hex
from agent_meta_seed_harness.providers.messages import MessagesProvider
from provider_wire import MODEL,wire

REF='artifact://sha256/'+'a'*64
PROVIDER=MessagesProvider(REF,MODEL,8)


def invocation(history=(),*,ordinal=None):
    bodies={'system':b'{"principle":"synthetic"}','task_input':b'{"provider":"messages","value":"redacted"}',
        'capability_schema':canonical_json([{'operation_id':'seed.echo','description':'Echo text','input_schema':{
            'type':'object','required':['value'],'properties':{'value':{'type':'string'}}}}]),
        'state_summary':b'{}','facts':b'[]'}
    assert tuple(bodies)==SECTION_IDS
    sections=tuple(Section(name,REF,'artifact://sha256/'+sha256_hex(body),len(body)) for name,body in bodies.items())
    rendered=SECTION_DELIMITER.join(bodies.values())
    manifest=ProjectionManifest('context://projection/01900000-0000-7000-8000-000000000001',REF,
        'composition://01900000-0000-7000-8000-000000000001',1,(SourceRef('artifact',REF,'a'*64),),
        sections,REF,'utf8-bytes/v1',len(rendered),16384)
    projection=ContextProjection(manifest,'artifact://sha256/'+sha256_hex(rendered),rendered)
    return ModelInvocation(SimpleNamespace(), 'synthetic-request',ordinal if ordinal is not None else sum(x.get('role')=='model' for x in history),projection,canonical_json(list(history)))


def model(*ids):
    return {'role':'model','response':json.loads(encode_model_response(ModelResponse(tuple(
        ToolCallPart(id,'seed.echo','{"value":"typed"}') for id in ids),'TOOL_CALL')))}


def tool(id,*,error=None):
    return {'role':'tool','call_id':id,'error_code':error,'content_hex':None if error else canonical_json({'value':'typed'}).hex()}


def test_projection_is_the_only_prompt_source_and_plan_is_deterministic_secretless():
    request=invocation()
    one,two=PROVIDER.prepare(request),PROVIDER.prepare(request)
    assert one==two and one.profile_artifact_id==REF
    body=json.loads(one.body)
    assert set(body)=={'model','system','messages','max_tokens','stream','tools'}
    assert body['stream'] is False and body['messages']==[{'role':'user','content':'{"provider":"messages","value":"redacted"}'}]
    assert body['tools'][0]['name']=='seed.echo' and body['max_tokens']==8
    assert PROVIDER.adapter().normalize(ProviderTerminalResponse(REF,wire())).parts==(TextPart('hello'),)


def test_parallel_wire_calls_become_one_ordered_user_result_message():
    history=[model('first','second'),tool('first'),tool('second',error=ErrorCode.AUTHORITY_DENIED)]
    body=json.loads(PROVIDER.prepare(invocation(history)).body)
    assert [m['role'] for m in body['messages']]==['user','assistant','user']
    calls=body['messages'][1]['content']; results=body['messages'][2]['content']
    assert [call['id'] for call in calls]==[result['tool_use_id'] for result in results]==['first','second']
    assert not results[0]['is_error'] and results[1]['is_error']
    assert json.loads(results[1]['content'])=={'error_code':ErrorCode.AUTHORITY_DENIED}
    assert all('usage' not in message for message in body['messages'])


@pytest.mark.parametrize('history',[ [tool('orphan')],[model('a')],
    [model('a','b'),tool('b'),tool('a')],[model('a'),tool('a'),tool('a')],
    [model('a'),tool('a'),model('a'),tool('a')],
    [model('a'),{**tool('a'),'content_hex':'FF'}],
    [model('a'),{**tool('a'),'error_code':'UNKNOWN_ERROR'}],
    [{'role':'unrecognized','payload':'synthetic-private-marker'}]])
def test_incomplete_reordered_duplicate_or_invalid_history_fails_before_a_plan(history):
    with pytest.raises(StableError) as caught:
        PROVIDER.prepare(invocation(history))
    assert caught.value.code==ErrorCode.INVALID_RESULT and 'synthetic-private-marker' not in str(caught.value)


@pytest.mark.parametrize('raw',[b'{}',b'[',b'['*33+b']'*33,b'[{"role":"tool","role":"tool"}]',b' '*(1024*1024+1)])
def test_bounded_canonical_history_is_required(raw):
    with pytest.raises(StableError):
        PROVIDER.prepare(replace(invocation(),history_content=raw))


def test_profile_substitution_and_model_ordinal_drift_are_refused():
    with pytest.raises(StableError):
        PROVIDER.normalize(ProviderTerminalResponse('artifact://sha256/'+'b'*64,wire()))
    with pytest.raises(StableError):
        PROVIDER.prepare(invocation(ordinal=1))
