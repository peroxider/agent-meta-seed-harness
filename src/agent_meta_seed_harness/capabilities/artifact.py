"""Artifact tool plans over the public Meta resource SPI (requires API 1.11)."""
import json

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.host import ArtifactRead, ArtifactPut, InvocationResult, ResourceAdapter
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex


def _arguments(request, fields):
    value = json.loads(request.call.arguments_json)
    if not isinstance(value, dict) or set(value) != set(fields):
        raise StableError(code=ErrorCode.INVALID_ARGUMENT, message='artifact tool arguments differ from schema')
    return value


def prepare_read(request):
    return ArtifactRead(_arguments(request, ('artifact_id',))['artifact_id'])


def prepare_put(request):
    value = _arguments(request, ('value',))['value']
    return ArtifactPut('seed_content', 'application/json', canonical_json(value))


def normalize(receipt):
    result = {'artifact_id':receipt.artifact_id, 'media_type':receipt.media_type,
        'size_bytes':len(receipt.content), 'sha256':sha256_hex(receipt.content)}
    if receipt.contract == 'artifact.read/v1':
        if receipt.media_type == 'application/json':
            result['content'] = {'kind':'json', 'value':json.loads(receipt.content)}
        elif receipt.media_type == 'text/plain; charset=utf-8':
            result['content'] = {'kind':'text', 'text':receipt.content.decode('utf-8')}
        else:
            raise StableError(code=ErrorCode.FEATURE_UNAVAILABLE, message='artifact serializer is unavailable')
    return InvocationResult(content=canonical_json(result))


read = ResourceAdapter(prepare_read, normalize)
put = ResourceAdapter(prepare_put, normalize)
