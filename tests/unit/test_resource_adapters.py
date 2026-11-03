"""Source development against Runtime API 1.11; not an installed S05 proof."""
import json
from types import SimpleNamespace

import pytest

from agent_meta_runtime.sdk import StableError
from agent_meta_runtime.sdk.host import ArtifactRead, ArtifactPut, StateRead, StateWrite, ResourceReceipt, ToolCallPart
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.capabilities import artifact, state

STATE = 'state://01900000-0000-7000-8000-000000000000'
REVISION = 'state-revision://01900000-0000-7000-8000-000000000001'
CONTENT = b'{"value":42}'
REF = 'artifact://sha256/' + sha256_hex(CONTENT)


def request(value):
    return SimpleNamespace(call=ToolCallPart('test','fixture',canonical_json(value).decode()))


def test_resource_plans_use_only_public_typed_requests():
    assert artifact.read.prepare(request({'artifact_id':REF})) == ArtifactRead(REF)
    assert artifact.put.prepare(request({'value':{'value':42}})) == ArtifactPut('seed_content','application/json',CONTENT)
    assert state.read.prepare(request({'state_id':STATE})) == StateRead(STATE)
    assert state.write.prepare(request({'state_id':STATE,'expected_state_revision_id':REVISION,'content_artifact_id':REF})) == StateWrite(STATE,REVISION,REF)


@pytest.mark.parametrize('adapter,arguments', [
    (artifact.read,{'path':'/forbidden'}), (artifact.read,{'artifact_id':REF,'extra':True}),
    (artifact.put,{'value':{},'media_type':'forbidden'}),
    (state.read,{'state_id':STATE,'latest':True}),
    (state.write,{'state_id':STATE,'content_artifact_id':REF}),
    (state.write,{'state_id':STATE,'expected_state_revision_id':REVISION,'content_artifact_id':REF,'force':True}),
])
def test_resource_plans_have_no_path_latest_force_or_undeclared_fields(adapter, arguments):
    with pytest.raises(StableError):
        adapter.prepare(request(arguments))


@pytest.mark.parametrize('contract', ['artifact.read/v1','artifact.put/v1','state.read/v1','state.write/v1'])
def test_normalizers_return_refs_to_exact_runtime_receipt_content(contract):
    receipt = ResourceReceipt(contract,REF,'application/json',CONTENT,
        STATE if contract.startswith('state.') else None, REVISION if contract.startswith('state.') else None)
    adapter = {'artifact.read/v1':artifact.read,'artifact.put/v1':artifact.put,
        'state.read/v1':state.read,'state.write/v1':state.write}[contract]
    output = json.loads(adapter.normalize(receipt).content)
    assert output.get('artifact_id',output.get('content_artifact_id')) == REF
    if contract == 'artifact.read/v1':
        assert output['content']=={'kind':'json','value':{'value':42}}
    if contract == 'state.read/v1':
        assert output['value']=={'value':42} and output['state_revision_id']==REVISION
