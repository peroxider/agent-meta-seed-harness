"""Pure public Host callbacks for the explicit terminal Messages profile."""
from dataclasses import dataclass
import json
import re

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import (
    JsonPart, TextPart, ToolCallPart, ProviderAdapter, ProviderRequestPlan,
    ProviderTerminalResponse, decode_model_response,
)
from agent_meta_runtime.sdk.packages import canonical_json
from .anthropic import normalize_terminal


def _invalid():
    return StableError(code=ErrorCode.INVALID_RESULT,message='invalid terminal Messages projection or history')


def _history(raw):
    try:
        if type(raw) is not bytes or len(raw)>1024*1024:
            raise ValueError('history size')
        value=json.loads(raw)
        if not isinstance(value,list) or len(value)>512 or canonical_json(value)!=raw:
            raise ValueError('history shape')
        pending,nodes=[(value,0)],0
        while pending:
            item,depth=pending.pop(); nodes+=1
            if depth>32 or nodes>16384:
                raise ValueError('history complexity')
            if isinstance(item,dict):
                pending.extend((part,depth+1) for part in item.values())
            elif isinstance(item,list):
                pending.extend((part,depth+1) for part in item)
        return value
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise _invalid() from None


@dataclass(frozen=True,slots=True)
class MessagesProvider:
    profile_artifact_id: str
    model_id: str
    maximum_output_tokens: int

    def __post_init__(self):
        # This public DTO validates identity/model/limit shape without a Task,
        # credential, endpoint or any transport selection.
        ProviderRequestPlan(self.profile_artifact_id,canonical_json({'model':self.model_id,
            'messages':[{'role':'user','content':'validation'}],
            'max_tokens':self.maximum_output_tokens,'stream':False}))

    def prepare(self, request):
        try:
            sections=rendered_sections(request.projection)
            system='\n\n'.join(sections[name].decode('utf-8') for name in ('system','state_summary','facts'))
            messages=[{'role':'user','content':sections['task_input'].decode('utf-8')}]
            tools=[]
            for operation in json.loads(sections['capability_schema']):
                tool={'name':operation['operation_id'],'input_schema':operation['input_schema']}
                if operation.get('description'):
                    tool['description']=operation['description']
                tools.append(tool)
            pending,seen,models=[],set(),0
            for entry in _history(request.history_content):
                if not isinstance(entry,dict):
                    raise ValueError('history entry')
                if entry.get('role')=='model' and set(entry)=={'role','response'}:
                    if pending or messages[-1]['role']!='user':
                        raise ValueError('serial model history')
                    response=decode_model_response(canonical_json(entry['response']))
                    blocks=[]
                    for part in response.parts:
                        if isinstance(part,TextPart):
                            blocks.append({'type':'text','text':part.text})
                        elif isinstance(part,JsonPart):
                            blocks.append({'type':'text','text':canonical_json(part.value).decode('utf-8')})
                        elif isinstance(part,ToolCallPart):
                            if part.call_id in seen:
                                raise ValueError('duplicate tool ID')
                            seen.add(part.call_id); pending.append(part.call_id)
                            blocks.append({'type':'tool_use','id':part.call_id,'name':part.name,'input':json.loads(part.arguments_json)})
                        else:
                            raise ValueError('unsupported Messages content')
                    messages.append({'role':'assistant','content':blocks}); models+=1
                elif entry.get('role')=='tool' and set(entry)=={'role','call_id','error_code','content_hex'}:
                    if not pending or entry['call_id']!=pending.pop(0):
                        raise ValueError('orphan or reordered tool result')
                    content=entry['content_hex']
                    if (entry['error_code'] is None)==(content is None):
                        raise ValueError('tool outcome')
                    if content is not None:
                        if not isinstance(content,str) or re.fullmatch(r'(?:[0-9a-f]{2})*',content) is None:
                            raise ValueError('tool content')
                        text=bytes.fromhex(content).decode('utf-8')
                    else:
                        if entry['error_code'] not in ErrorCode.ALL:
                            raise ValueError('tool error')
                        text=canonical_json({'error_code':entry['error_code']}).decode('utf-8')
                    block={'type':'tool_result','tool_use_id':entry['call_id'],'content':text,'is_error':entry['error_code'] is not None}
                    if messages[-1]['role']=='user':
                        messages[-1]['content'].append(block)
                    else:
                        messages.append({'role':'user','content':[block]})
                else:
                    raise ValueError('history role')
            if pending or models!=request.ordinal or messages[-1]['role']!='user':
                raise ValueError('incomplete history')
            body={'model':self.model_id,'system':system,'messages':messages,'max_tokens':self.maximum_output_tokens,'stream':False}
            if tools:
                body['tools']=tools
            return ProviderRequestPlan(self.profile_artifact_id,canonical_json(body))
        except (ValueError,KeyError,TypeError,AttributeError,UnicodeError,RecursionError,StableError):
            raise _invalid() from None

    def normalize(self, terminal):
        if type(terminal) is not ProviderTerminalResponse or terminal.profile_artifact_id!=self.profile_artifact_id:
            raise _invalid()
        return normalize_terminal(terminal.content,expected_model=self.model_id)

    def adapter(self):
        return ProviderAdapter(self.prepare,self.normalize)
