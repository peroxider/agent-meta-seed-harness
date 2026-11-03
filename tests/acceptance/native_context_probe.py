"""Explicit optional-asset job; run this file directly with pytest, not default CI.

SEED_NATIVE_CONTEXT_TOKENIZER_JSON must name the pinned public vocabulary.
The real installed native Root/SDK/CLI path is tested with the fake Provider;
no upstream model request, private Runtime import, DB/CAS or key read occurs.
"""
import asyncio
import json
import os
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.context import glm53_context_tokenizer_descriptor
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.providers.tokenizer import load_glm53flash_text_encoder, tokenizer_lock
from seed_package import seed_bundle, install_seed, wait_ready
from seed_runtime import admin, daemon_process


@pytest.mark.parametrize('native_enabled',[True,False])
def test_real_native_root_context_is_independently_counted_or_refused_before_model(tmp_path,native_enabled):
    configured=os.environ.get('SEED_NATIVE_CONTEXT_TOKENIZER_JSON')
    assert configured, 'explicit pinned tokenizer input is required; this optional job cannot report a skip as success'
    path=Path(configured)
    expected=tokenizer_lock()['files']['tokenizer.json']
    with path.open('rb') as stream:
        raw=stream.read(expected['bytes']+1)
    encoder=load_glm53flash_text_encoder(raw)
    descriptor=glm53_context_tokenizer_descriptor()
    assert descriptor['tokenizer_id']==encoder.tokenizer_id and descriptor['vocabulary_sha256']==sha256_hex(raw)
    bundle,publisher=seed_bundle(context_tokenizer_descriptor=descriptor)
    manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    assert manifest['public_api_range']=='>=1.16.0 <2.0.0'
    assert max(len(value) for value in bundle.artifacts.values())<1024*1024
    with daemon_process(tmp_path,publishers=[publisher],context_tokenizer_json=path if native_enabled else None) as owner:
        install_seed(owner.data_dir,tmp_path,bundle)
        asyncio.run(wait_ready(owner.data_dir))
        task_input=tmp_path/'input.json'
        task_input.write_bytes(canonical_json({'provider':'fake','scenario':'terminal','value':'你好，原生计数 Bearer NATIVE_CONTEXT_CANARY'}))
        reference=admin(owner.data_dir,'artifact','put',str(task_input),'--kind','task_input')['artifact_id']
        task=admin(owner.data_dir,'task','submit','--input-artifact',reference)
        async def inspect():
            client=await connect(owner.data_dir)
            try:
                result,done=await client.wait_task(task['task_id'],timeout_s=10)
                assert done
                execution=await client.get_task_execution(task['task_id'])
                if not native_enabled:
                    assert result['error']=='FAILED_PRECONDITION',result
                    assert not execution['invocations'] and not execution['projections']
                    return
                assert result['status']=='SUCCEEDED',result
                assert execution['consumed_budget']['model_calls']==1
                assert len(execution['invocations'])==1 and execution['invocations'][0]['status']=='SUCCEEDED'
                assert len(execution['projections'])==1
                stored=execution['projections'][0]
                body=await client.get_artifact_content(stored['rendered_artifact_id'])
                assert stored['rendered_artifact_id']=='artifact://sha256/'+sha256_hex(body)
                assert stored['manifest']['tokenizer_id']==encoder.tokenizer_id
                assert stored['manifest']['total_tokens']==encoder.count(body.decode('utf-8'))!=len(body)
                assert b'NATIVE_CONTEXT_CANARY' not in body and b'[REDACTED]' in body
                for section in stored['manifest']['sections']:
                    content=await client.get_artifact_content(section['output_artifact_id'])
                    assert section['token_count']==encoder.count(content.decode('utf-8'))
                assert stored['manifest']['total_tokens']<=stored['manifest']['budget_tokens']
            finally:
                await client.aclose()
        asyncio.run(inspect())
