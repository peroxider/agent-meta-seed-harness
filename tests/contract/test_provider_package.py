"""Explicit signed Provider profile/package identity, no transport side effects."""
import json

import pytest

from agent_meta_runtime.sdk.packages import decode_package,sha256_hex
from agent_meta_seed_harness.packaging import PROVIDER_EXECUTION_SOURCE_PATHS
from provider_host_fixture import provider_inputs,provider_bundle


def test_provider_source_and_profile_are_signed_without_replacing_minimal_binding():
    configuration,artifacts=provider_inputs()
    bundle,publisher=provider_bundle(configuration,artifacts)
    reverse,_=provider_bundle(dict(reversed(list(configuration.items()))),dict(reversed(list(artifacts.items()))))
    assert bundle==reverse
    manifest=json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    package,source=decode_package(bundle.artifacts[bundle.package_artifact_id])
    assert package.package.entrypoint=='agent_meta_seed_harness.host_binding_provider:create'
    assert package.package.runtime_constraints['provider_profile_artifact_id']==configuration['profile_artifact_id']
    assert manifest['public_api_range']=='>=1.9.0 <2.0.0'
    assert set(source)==set(PROVIDER_EXECUTION_SOURCE_PATHS)|{'agent_meta_seed_harness/provider_config.py'}
    assert 'agent_meta_seed_harness/providers/fake.py' not in source
    descriptors=[json.loads(bundle.artifacts[ref]) for ref in manifest['capability_descriptor_artifact_ids']]
    model=next(item for item in descriptors if item['capability_id']=='capability://seed.messages-model')
    assert model['runtime_constraints']['provider_profile_artifact_id']==configuration['profile_artifact_id']
    assert all(key not in source['agent_meta_seed_harness/provider_config.py'].decode() for key in ('credential','endpoint','Authorization'))


@pytest.mark.parametrize('kind',['unrelated','missing','hash','wrong_model','too_much_output','credential'])
def test_builder_refuses_unrelated_content_or_unbound_provider_configuration(kind):
    configuration,artifacts=provider_inputs()
    if kind=='unrelated':
        artifacts['artifact://sha256/'+sha256_hex(b'unrelated')]=b'unrelated'
    elif kind=='missing':
        del artifacts[json.loads(artifacts[configuration['profile_artifact_id']])['egress_policy_artifact_id']]
    elif kind=='hash':
        artifacts[configuration['profile_artifact_id']]=b'{}'
    elif kind=='wrong_model':
        configuration['model_id']='different-model'
    elif kind=='too_much_output':
        configuration['maximum_output_tokens']=33
    else:
        configuration['credential_handle']='synthetic-forbidden-handle'
    with pytest.raises(ValueError):
        provider_bundle(configuration,artifacts)
