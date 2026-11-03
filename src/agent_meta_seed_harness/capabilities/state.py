"""Frozen State reads and CAS write plans; Runtime owns all commits/overlays."""
import json

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.host import StateRead, StateWrite, InvocationResult, ResourceAdapter
from agent_meta_runtime.sdk.packages import canonical_json


def _arguments(request, fields):
    value = json.loads(request.call.arguments_json)
    if not isinstance(value, dict) or set(value) != set(fields):
        raise StableError(code=ErrorCode.INVALID_ARGUMENT, message='state tool arguments differ from schema')
    return value


def prepare_read(request):
    return StateRead(_arguments(request, ('state_id',))['state_id'])


def prepare_write(request):
    value = _arguments(request, ('state_id','expected_state_revision_id','content_artifact_id'))
    return StateWrite(value['state_id'], value['expected_state_revision_id'], value['content_artifact_id'])


def normalize(receipt):
    if receipt.media_type != 'application/json':
        raise StableError(code=ErrorCode.FEATURE_UNAVAILABLE, message='state serializer is unavailable')
    value = {'state_id':receipt.state_id,'state_revision_id':receipt.state_revision_id,
        'content_artifact_id':receipt.artifact_id}
    if receipt.contract == 'state.read/v1':
        value['value'] = json.loads(receipt.content)
    return InvocationResult(content=canonical_json(value))


read = ResourceAdapter(prepare_read, normalize)
write = ResourceAdapter(prepare_write, normalize)
