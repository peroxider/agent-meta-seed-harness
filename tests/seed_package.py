"""Build/install the consumer's own signed package through published APIs."""

from importlib.resources import files
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json, manifest_signature_preimage, sha256_hex
from agent_meta_seed_harness.packaging import EXECUTION_SOURCE_PATHS, TOOLS_EXECUTION_SOURCE_PATHS, PackageBundle, build_bundle, load_bundle, require_bundle_inputs

from seed_runtime import admin


def seed_bundle(*, overrides=None, **build_options):
    root = Path(__file__).resolve().parents[1]
    paths = TOOLS_EXECUTION_SOURCE_PATHS if build_options.get('tools') else EXECUTION_SOURCE_PATHS
    source = {name: files("agent_meta_seed_harness").joinpath(name.split("/", 1)[1]).read_bytes() for name in paths}
    source.update(overrides or {})
    supplied = os.environ.get('SEED_TOOLS_CONSUMER_BUNDLE') if build_options.get('tools') else os.environ.get("SEED_CONSUMER_BUNDLE")
    if supplied and overrides is None and (not build_options or build_options == {'tools':True}):
        bundle = load_bundle(Path(supplied))
        require_bundle_inputs(bundle, files=source, dependency_lock=(root / "requirements-ci.lock").read_bytes(),
            contract_bundle_sha256=sha256_hex((root / "docs/runtime-contract/manifest.json").read_bytes()))
        manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        return bundle, sha256_hex(bundle.artifacts[manifest["publisher_identity_artifact_id"]])
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    bundle = build_bundle(files=source, dependency_lock=(root / "requirements-ci.lock").read_bytes(),
        publisher_public_key=key.public_key().public_bytes_raw(), signer=key,
        contract_bundle_sha256=sha256_hex((root / "docs/runtime-contract/manifest.json").read_bytes()), **build_options)
    return bundle, sha256_hex(key.public_key().public_bytes_raw())


def limit_activation_grant(bundle, *, permission, max_uses):
    """Sign a consumer-owned restricted policy with the public fixture publisher."""
    artifacts = dict(bundle.artifacts)
    manifest = json.loads(artifacts[bundle.manifest_artifact_id])
    grants = json.loads(artifacts[manifest["grant_requests_artifact_id"]])
    matches = [request for request in grants["requests"] if request["permission"] == permission]
    assert len(matches) == 1
    matches[0]["max_uses"] = max_uses
    def add(raw):
        reference = "artifact://sha256/" + sha256_hex(raw)
        artifacts[reference] = raw
        return reference
    manifest["grant_requests_artifact_id"] = add(canonical_json(grants))
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    manifest["signature_artifact_id"] = add(key.sign(manifest_signature_preimage(manifest)))
    return PackageBundle(add(canonical_json(manifest)), bundle.package_artifact_id, artifacts)


def install_seed(data_dir, root, bundle, *, activate=True):
    artifacts = root / "consumer-artifacts"
    artifacts.mkdir(exist_ok=True)
    for reference, raw in bundle.artifacts.items():
        path = artifacts / reference.rsplit("/", 1)[1]
        path.write_bytes(raw)
        assert admin(data_dir, "artifact", "put", str(path), "--kind", "code")["artifact_id"] == reference
    report = admin(data_dir, "harness", "validate", bundle.manifest_artifact_id)
    assert report["valid"], report
    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    installed = admin(data_dir, "harness", "install", "--name", manifest["package_name"], "--version", manifest["package_version"],
        bundle.manifest_artifact_id, bundle.package_artifact_id)
    if activate:
        activate_seed(data_dir, bundle, installed["harness_id"])
    return installed["harness_id"]


def activate_seed(data_dir, bundle, harness_id):
    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    requests = json.loads(bundle.artifacts[manifest["grant_requests_artifact_id"]])["requests"]
    grants = [argument for request in requests for argument in ("--grant", canonical_json(request).decode())]
    return admin(data_dir, "harness", "activate", harness_id, manifest["composition_template_artifact_id"], *grants)


async def wait_ready(data_dir, *, revision=None):
    import asyncio
    client = await connect(data_dir)
    try:
        end = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < end:
            info = await client.get_info()
            if info.serving_ready and (revision is None or info.serving_revision == revision):
                return
            await asyncio.sleep(.02)
        raise AssertionError(f"Seed did not become serving-ready: {info}")
    finally:
        await client.aclose()
