"""Deterministic AMPAK + signed Harness manifest construction.

All Runtime contract operations use the public SDK. Private signing-key
material is supplied by the caller and is never written into the bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Protocol

from agent_meta_runtime.sdk.packages import (
    PackageMeta, build_manifest, canonical_json, encode_package,
    decode_package, manifest_signature_preimage, sha256_hex, validate_manifest, validate_loop_policy,
)
from agent_meta_runtime.sdk.context import build_context_artifacts


EXECUTION_SOURCE_PATHS = tuple("agent_meta_seed_harness/" + path for path in (
    "__init__.py", "host_binding.py", "loop.py", "context.py", "providers/__init__.py", "providers/fake.py",
    "capabilities/__init__.py", "capabilities/echo.py"))

PROVIDER_EXECUTION_SOURCE_PATHS = tuple(path for path in EXECUTION_SOURCE_PATHS
    if path not in ('agent_meta_seed_harness/host_binding.py','agent_meta_seed_harness/providers/fake.py')) + tuple(
    'agent_meta_seed_harness/'+path for path in ('host_binding_provider.py','providers/anthropic.py','providers/messages.py'))

_TOOL_ADAPTER_PATHS = tuple('agent_meta_seed_harness/capabilities/' + path for path in ('artifact.py', 'state.py', 'scratch.py', 'transform.py', 'bindings.py'))
TOOLS_EXECUTION_SOURCE_PATHS = tuple(path for path in EXECUTION_SOURCE_PATHS if path not in (
    'agent_meta_seed_harness/host_binding.py', 'agent_meta_seed_harness/providers/fake.py')) + _TOOL_ADAPTER_PATHS + (
    'agent_meta_seed_harness/host_binding_tools.py', 'agent_meta_seed_harness/providers/fake_tools.py')
PROVIDER_TOOLS_EXECUTION_SOURCE_PATHS = tuple(path for path in PROVIDER_EXECUTION_SOURCE_PATHS
    if path != 'agent_meta_seed_harness/host_binding_provider.py') + _TOOL_ADAPTER_PATHS + (
    'agent_meta_seed_harness/host_binding_tools_provider.py',)


class PublisherSigner(Protocol):
    def sign(self, data: bytes) -> bytes: ...


@dataclass(frozen=True)
class PackageBundle:
    manifest_artifact_id: str
    package_artifact_id: str
    artifacts: Mapping[str, bytes]

    def write(self, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        artifact_dir = destination / "artifacts"
        artifact_dir.mkdir(exist_ok=True)
        for ref, raw in sorted(self.artifacts.items()):
            expected = "artifact://sha256/" + sha256_hex(raw)
            if ref != expected:
                raise ValueError("bundle ArtifactId/content mismatch")
            path = artifact_dir / ref.rsplit("/", 1)[1]
            if path.exists() and path.read_bytes() != raw:
                raise ValueError("refusing to replace a different artifact")
            path.write_bytes(raw)
        (destination / "bundle.json").write_bytes(canonical_json({
            "schema": "seed-package-bundle/v1",
            "manifest_artifact_id": self.manifest_artifact_id,
            "package_artifact_id": self.package_artifact_id,
            "artifact_ids": sorted(self.artifacts),
        }))
        (destination / "package.ampak").write_bytes(self.artifacts[self.package_artifact_id])
        # Named review copies are derived from the same content-addressed
        # artifacts. There is no second hand-maintained policy/template source.
        manifest = json.loads(self.artifacts[self.manifest_artifact_id])
        for filename, reference in {
            "manifest.json": self.manifest_artifact_id,
            "composition.json": manifest["composition_template_artifact_id"],
            "loop-policy.json": manifest["loop_policy_artifact_id"],
            "grant-requests.json": manifest["grant_requests_artifact_id"],
            "provenance.json": manifest["build_provenance_artifact_id"],
            "publisher.ed25519.pub": manifest["publisher_identity_artifact_id"],
            "signature.ed25519": manifest["signature_artifact_id"],
        }.items():
            (destination / filename).write_bytes(self.artifacts[reference])
        descriptors = destination / "capabilities"
        descriptors.mkdir(exist_ok=True)
        for index, reference in enumerate(manifest["capability_descriptor_artifact_ids"]):
            (descriptors / f"{index:03d}.json").write_bytes(self.artifacts[reference])
        package, _ = decode_package(self.artifacts[self.package_artifact_id])
        (destination / "dependency-lock.txt").write_bytes(self.artifacts[package.package.dependency_lock_artifact_id])


def load_bundle(marker_path: Path) -> PackageBundle:
    """Read an explicitly supplied signed bundle; never read a signing key."""
    marker_path = Path(marker_path).resolve(strict=True)
    if marker_path.stat().st_size > 1024 * 1024:
        raise ValueError("bundle marker exceeds byte ceiling")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate bundle marker field")
            result[key] = value
        return result
    marker = json.loads(marker_path.read_bytes(), object_pairs_hook=pairs)
    if not isinstance(marker, dict) or set(marker) != {"schema", "manifest_artifact_id", "package_artifact_id", "artifact_ids"} or marker["schema"] != "seed-package-bundle/v1":
        raise ValueError("invalid bundle marker")
    ids = marker["artifact_ids"]
    if not isinstance(ids, list) or not 0 < len(ids) <= 4096 or not all(isinstance(v, str) and re.fullmatch(r"artifact://sha256/[0-9a-f]{64}", v) for v in ids) or ids != sorted(set(ids)):
        raise ValueError("invalid bundle Artifact identities")
    blobs, total = {}, 0
    base = marker_path.parent
    for reference in ids:
        path = base / "artifacts" / reference.rsplit("/", 1)[1]
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(base):
            raise ValueError("bundle Artifact escapes supplied directory")
        total += path.stat().st_size
        if total > 64 * 1024 * 1024:
            raise ValueError("bundle exceeds byte ceiling")
        raw = path.read_bytes()
        if reference != "artifact://sha256/" + sha256_hex(raw):
            raise ValueError("bundle Artifact hash mismatch")
        blobs[reference] = raw
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    try:
        manifest_id, package_id = marker["manifest_artifact_id"], marker["package_artifact_id"]
        manifest = json.loads(blobs[manifest_id], object_pairs_hook=pairs)
        if validate_manifest(manifest) or manifest["package_artifact_id"] != package_id:
            raise ValueError("invalid supplied Harness manifest")
        Ed25519PublicKey.from_public_bytes(blobs[manifest["publisher_identity_artifact_id"]]).verify(
            blobs[manifest["signature_artifact_id"]], manifest_signature_preimage(manifest))
        package, _ = decode_package(blobs[package_id])
        for reference in (package.package.contract_artifact_id, package.package.dependency_lock_artifact_id,
            package.package.build_provenance_artifact_id, manifest["composition_template_artifact_id"],
            manifest["grant_requests_artifact_id"], manifest["loop_policy_artifact_id"], *manifest["capability_descriptor_artifact_ids"]):
            if reference not in blobs:
                raise ValueError("supplied bundle closure is incomplete")
    except (KeyError, TypeError, InvalidSignature) as exc:
        raise ValueError("supplied bundle content/signature/closure is invalid") from exc
    return PackageBundle(manifest_id, package_id, MappingProxyType(blobs))


def require_bundle_inputs(bundle: PackageBundle, *, files: Mapping[str, bytes], dependency_lock: bytes, contract_bundle_sha256: str):
    """Require final execution source/lock/provenance before consumer install."""
    package, actual = decode_package(bundle.artifacts[bundle.package_artifact_id])
    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    if dict(actual) != dict(files) or bundle.artifacts[package.package.dependency_lock_artifact_id] != dependency_lock:
        raise ValueError("supplied bundle differs from final execution source or lock")
    if package.package.build_provenance_artifact_id != manifest["build_provenance_artifact_id"]:
        raise ValueError("supplied bundle provenance identities differ")
    provenance = json.loads(bundle.artifacts[manifest["build_provenance_artifact_id"]])
    if provenance.get("contract_bundle_sha256") != contract_bundle_sha256 or provenance.get("source_files") != {name: sha256_hex(raw) for name, raw in sorted(files.items())}:
        raise ValueError("supplied bundle provenance differs from final inputs")


def build_bundle(
    *,
    files: Mapping[str, bytes],
    dependency_lock: bytes,
    publisher_public_key: bytes,
    signer: PublisherSigner,
    contract_bundle_sha256: str,
    version: str = "0.1.0-dev.1",
    entrypoint: str = "agent_meta_seed_harness.host_binding:create",
    loop_policy: Mapping | None = None,
    descriptor_revision: int = 1,
    provider_configuration: Mapping | None = None,
    provider_artifacts: Mapping[str,bytes] | None = None,
    tools: bool = False,
    context_tokenizer_descriptor: Mapping | None = None,
) -> PackageBundle:
    if context_tokenizer_descriptor is not None and provider_configuration is not None:
        raise ValueError('native Context needs a separately verified Provider request tokenizer before real Provider integration')
    if type(tools) is not bool:
        raise ValueError('tools selection must be a boolean')
    if len(publisher_public_key) != 32:
        raise ValueError("publisher key must be 32 raw Ed25519 bytes")
    if len(contract_bundle_sha256) != 64 or any(c not in "0123456789abcdef" for c in contract_bundle_sha256):
        raise ValueError("contract bundle hash must be lowercase SHA-256")
    loop_policy = dict(loop_policy) if loop_policy is not None else {"schema": "harness-loop-policy/v1",
        "max_turns": 8, "max_steps": 40, "max_model_calls": 8, "stop_on_tool_error": True}
    if validate_loop_policy(loop_policy):
        raise ValueError("invalid Seed loop policy")
    if type(descriptor_revision) is not int or descriptor_revision < 1:
        raise ValueError("descriptor revision must be a positive integer")
    artifacts = {}
    files = dict(files)
    provider = None
    if provider_configuration is not None:
        from .providers.messages import MessagesProvider
        if set(provider_configuration)!={'profile_artifact_id','model_id','maximum_output_tokens'}:
            raise ValueError('Provider configuration must contain only profile/model/output identity')
        provider = MessagesProvider(**provider_configuration)
        for reference,raw in (provider_artifacts or {}).items():
            if type(raw) is not bytes or reference!='artifact://sha256/'+sha256_hex(raw):
                raise ValueError('Provider Artifact identity differs')
            artifacts[reference]=raw
        try:
            raw=artifacts[provider.profile_artifact_id]
            if not 0<len(raw)<=1024*1024:
                raise ValueError('Provider profile size')
            declaration=json.loads(raw)
            fields={'schema','protocol','model_id','parameter_allowlist','context_window_tokens','maximum_output_tokens',
                'maximum_request_bytes','maximum_response_bytes','timeout_us','egress_policy_artifact_id',
                'tokenizer_artifact_id','price_policy_artifact_id','lookup_policy','usage_mapping'}
            if (not isinstance(declaration,dict) or set(declaration)!=fields or canonical_json(declaration)!=raw
                    or declaration['schema']!='provider-profile/v1' or declaration['protocol']!='anthropic-messages-terminal/v1'
                    or declaration['lookup_policy']!='UNAVAILABLE_NO_RETRY' or declaration['usage_mapping']!='anthropic-messages-usage/v1'
                    or declaration['model_id']!=provider.model_id
                    or provider.maximum_output_tokens>declaration['maximum_output_tokens']):
                raise ValueError('Provider declaration differs')
            closure={provider.profile_artifact_id,declaration['egress_policy_artifact_id']}
            closure.update(declaration[key] for key in ('tokenizer_artifact_id','price_policy_artifact_id') if declaration[key] is not None)
            if set(artifacts)!=closure:
                raise ValueError('Provider closure is missing or includes unrelated Artifacts')
            shapes={
                'egress_policy_artifact_id':('provider-egress/v1',{'schema','scheme','host','port','path','networks','profile'}),
                'tokenizer_artifact_id':('provider-tokenizer/v1',{'schema','model_id','algorithm','tokenizer_id'}),
                'price_policy_artifact_id':('provider-price/v1',{'schema','currency','pricing_version','input_microunits_per_million_tokens',
                    'output_microunits_per_million_tokens','minimum_cost_microunits','rounding'}),
            }
            for key,(schema,keys) in shapes.items():
                if declaration[key] is None:
                    if key=='egress_policy_artifact_id':
                        raise ValueError('egress policy is required')
                    continue
                raw=artifacts[declaration[key]]
                if not 0<len(raw)<=1024*1024:
                    raise ValueError('Provider dependency size')
                value=json.loads(raw)
                if not isinstance(value,dict) or set(value)!=keys or value['schema']!=schema or canonical_json(value)!=raw:
                    raise ValueError('Provider dependency schema')
                if key=='tokenizer_artifact_id' and value['model_id']!=provider.model_id:
                    raise ValueError('Provider tokenizer model binding')
        except (KeyError,TypeError,ValueError,RecursionError):
            raise ValueError('explicit canonical Provider profile is required') from None
        if entrypoint!='agent_meta_seed_harness.host_binding:create':
            raise ValueError('Provider package requires its explicit Provider binding')
        entrypoint='agent_meta_seed_harness.host_binding_tools_provider:create' if tools else 'agent_meta_seed_harness.host_binding_provider:create'
        config_path='agent_meta_seed_harness/provider_config.py'
        if config_path in files:
            raise ValueError('generated Provider configuration cannot be overridden')
        files[config_path]=('CONFIGURATION = '+repr({key:provider_configuration[key] for key in sorted(provider_configuration)})+'\n').encode('utf-8')
    elif provider_artifacts is not None:
        raise ValueError('Provider Artifacts require an explicit Provider configuration')
    elif tools:
        if entrypoint != 'agent_meta_seed_harness.host_binding:create':
            raise ValueError('tools package requires its explicit tools binding')
        entrypoint = 'agent_meta_seed_harness.host_binding_tools:create'

    def add(raw: bytes) -> str:
        ref = "artifact://sha256/" + sha256_hex(raw)
        artifacts[ref] = raw
        return ref

    def document(body: dict) -> str:
        return add(canonical_json(body))

    contract = document({"schema": "harness-contract/v1", "version": "1.1.0"})
    lock = add(dependency_lock)
    from . import toolset
    task_schema = {"type": "object", "required": ["provider"], "properties": {
            "provider": {"const": "messages" if provider is not None else "fake"}, "scenario": {"type": "string"},
            "value": {"type": "string", "maxLength": 4096}}, "additionalProperties": False}
    if tools and provider is None:
        task_schema = toolset.input_schema()
    context_profile, context_artifacts = build_context_artifacts(
        input_schema=task_schema, selected_operation_ids=["seed.echo", *toolset.OPERATIONS] if tools else ["seed.echo"],
        provider_id=provider.model_id if provider is not None else 'fake-tools' if tools else "fake", budget_tokens=16_384,
        **({'tokenizer_descriptor':dict(context_tokenizer_descriptor)} if context_tokenizer_descriptor is not None else {}))
    artifacts.update(context_artifacts)
    provenance = document({
        "schema": "seed-build-provenance/v1",
        "source_files": {path: sha256_hex(raw) for path, raw in sorted(files.items())},
        "dependency_lock_artifact_id": lock,
        "contract_bundle_sha256": contract_bundle_sha256,
        "builder": "agent-meta-seed-harness/0.1.0.dev1",
        "context_profile_artifact_id": context_profile,
    })
    meta = PackageMeta(
        name="agent-meta-seed-harness", version=version, artifact_kind="harness",
        entrypoint=entrypoint, contract_artifact_id=contract,
        dependency_lock_artifact_id=lock, state_schema_artifact_ids=(),
        migration_artifact_ids=(), runtime_constraints={"python": ">=3.12 <3.13", "context_profile_artifact_id": context_profile,
            **({'provider_profile_artifact_id':provider.profile_artifact_id} if provider is not None else {})},
        platform_constraints={}, build_provenance_artifact_id=provenance,
    )
    package = add(encode_package(build_manifest(meta, files), files))
    object_schema = document({"type": "object"})
    echo_schema = document({"type": "object", "required": ["value"], "properties": {"value": {"type": "string", "maxLength": 4096}}, "additionalProperties": False})
    descriptors, slots, requests = [], {}, []
    for slot, capability, invoke, permission, effects, schema in (
        ("model", "capability://seed.messages-model" if provider is not None else "capability://seed.fake-model",
            "seed.messages-model" if provider is not None else "seed.fake-model", "model.invoke", ["model.invoke"], object_schema),
        ("echo", "capability://seed.echo", "seed.echo", "capability.invoke", ["none"], echo_schema),
    ):
        def operation(name, permissions, operation_effects, operation_schema, pure):
            return {"operation_id": name, "input_schema_artifact_id": operation_schema, "output_schema_artifact_id": operation_schema,
                "effects": operation_effects, "required_permissions": permissions, "idempotency": "PURE" if pure else "NONE", "retry_semantics": "NEVER"}
        descriptor = {"capability_id": capability, "descriptor_revision": descriptor_revision, "artifact_id": package,
            "placement": "in_process", "trust_class": "builtin_or_signed", "provides": [], "requires": [],
            "operations": [operation("probe." + slot, [], ["none"], object_schema, True), operation(invoke, [permission], effects, schema, slot == "echo")]}
        if slot=='model' and provider is not None:
            descriptor['runtime_constraints']={'provider_profile_artifact_id':provider.profile_artifact_id}
        descriptors.append(document(descriptor))
        slots[slot] = {"capability_id": capability, "descriptor_revision": descriptor_revision, "artifact_id": package, "placement": "in_process",
            "criticality": "REQUIRED", "degradation_policy": "REJECT_TASK", "health_probe": {"operation_id": "probe." + slot}}
        requests.append({"permission": permission, "scope": {"realm_id": "realm://main", "targets": [{"type": "CAPABILITY", "id": capability}]}})
    if tools:
        grouped = {}
        for slot, name, input_ref, output_ref, effects, permissions, idempotency, resource in toolset.declarations(document):
            item = {'operation_id': name, 'input_schema_artifact_id': input_ref, 'output_schema_artifact_id': output_ref,
                'effects': effects, 'required_permissions': permissions, 'idempotency': idempotency, 'retry_semantics': 'NEVER'}
            if resource is not None:
                item['resource_contract'] = resource
            grouped.setdefault(slot, []).append(item)
        def grant(permission, target_type, identifier):
            requests.append({'permission': permission, 'scope': {'realm_id': 'realm://main',
                'targets': [{'type': target_type, 'id': identifier}]}})
        for slot, operations in grouped.items():
            capability = 'capability://seed.' + slot
            probe = {'operation_id': 'probe.' + slot, 'input_schema_artifact_id': object_schema, 'output_schema_artifact_id': object_schema,
                'effects': ['none'], 'required_permissions': [], 'idempotency': 'PURE', 'retry_semantics': 'NEVER'}
            descriptors.append(document({'capability_id': capability, 'descriptor_revision': descriptor_revision, 'artifact_id': package,
                'placement': 'in_process', 'trust_class': 'builtin_or_signed', 'provides': [], 'requires': [], 'operations': [probe, *operations]}))
            slots[slot] = {'capability_id': capability, 'descriptor_revision': descriptor_revision, 'artifact_id': package,
                'placement': 'in_process', 'criticality': 'REQUIRED', 'degradation_policy': 'REJECT_TASK', 'health_probe': {'operation_id': 'probe.' + slot}}
            grant('capability.invoke', 'CAPABILITY', capability)
            if slot == 'scratch':
                for permission in sorted({permission for operation in operations for permission in operation['required_permissions']}):
                    grant(permission, 'CAPABILITY', capability)
        for permission in ('capability.invoke', 'artifact.put'):
            grant(permission, 'ARTIFACT_KIND', 'seed_content')
        for permission in ('state.read', 'state.write'):
            grant(permission, 'CAPABILITY', 'capability://seed.state')
        for kind in ('seed_scratch_source', 'seed_scratch_input', 'scratch_output', 'scratch_observation', 'resource_content'):
            grant('capability.invoke', 'ARTIFACT_KIND', kind)
    composition = document({"schema": "composition/v1", "realm_id": "realm://main", "slots": slots, "wiring": []})
    grants = document({"schema": "harness-grant-requests/v1", "requests": requests})
    policy = document(loop_policy)
    manifest = {
        "schema": "harness-package/v1", "package_name": meta.name,
        "package_version": meta.version, "package_artifact_id": package,
        "publisher_identity_artifact_id": add(publisher_public_key),
        # The signature field is excluded from the signing preimage.
        "signature_artifact_id": "artifact://sha256/" + "0" * 64,
        "public_api_range": ">=1.16.0 <2.0.0" if context_tokenizer_descriptor is not None else ">=1.15.0 <2.0.0" if tools else ">=1.9.0 <2.0.0" if provider is not None else ">=1.0.0 <2.0.0", "harness_contract_range": ">=1.1.0 <2.0.0",
        "capability_contract_range": ">=1.1.0 <2.0.0" if tools else ">=1.0.0 <2.0.0", "artifact_format": "AMPAK1",
        "capability_descriptor_artifact_ids": sorted(descriptors), "composition_template_artifact_id": composition,
        "grant_requests_artifact_id": grants, "loop_policy_artifact_id": policy,
        "required_backend_features": [], "optional_backend_features": [],
        "build_provenance_artifact_id": provenance,
    }
    signature = signer.sign(manifest_signature_preimage(manifest))
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise ValueError("signer must return a 64-byte Ed25519 signature")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        Ed25519PublicKey.from_public_bytes(publisher_public_key).verify(signature, manifest_signature_preimage(manifest))
    except InvalidSignature as exc:
        raise ValueError("publisher signer does not match the declared public key") from exc
    manifest["signature_artifact_id"] = add(signature)
    issues = validate_manifest(manifest)
    if issues:
        raise ValueError(f"invalid Harness manifest: {issues}")
    manifest_id = document(manifest)
    return PackageBundle(manifest_id, package, MappingProxyType(artifacts))
