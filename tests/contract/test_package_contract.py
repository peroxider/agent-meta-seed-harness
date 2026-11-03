"""S01 deterministic packaging and public installed-wheel validation proofs.

The Runtime process is accessed only through the public SDK/CLI. Its keys,
database, CAS and source checkout are never inspected by this consumer suite.
"""

import asyncio
from importlib.resources import files
import json
from pathlib import Path
import shutil

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import (
    AmpakError, canonical_json, decode_package, manifest_signature_preimage, sha256_hex,
)
from agent_meta_seed_harness.packaging import EXECUTION_SOURCE_PATHS, build_bundle, PackageBundle
from seed_runtime import admin, invoke, running_daemon


def build(**overrides):
    # Explicitly public test publisher; never used for a release.
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    args = dict(files={"agent_meta_seed_harness/probe.py": b"async def run():\n    return None\n"}, entrypoint="agent_meta_seed_harness.probe:run", dependency_lock=b"fixed lock\n", publisher_public_key=key.public_key().public_bytes_raw(), signer=key, contract_bundle_sha256="a" * 64)
    args.update(overrides)
    return build_bundle(**args)


def test_package_payload_and_signed_manifest_are_deterministic():
    first, second = build(), build()
    assert first == second
    assert dict(first.artifacts) == dict(second.artifacts)
    manifest = json.loads(first.artifacts[first.manifest_artifact_id])
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    key.public_key().verify(first.artifacts[manifest["signature_artifact_id"]], manifest_signature_preimage(manifest))
    package, files = decode_package(first.artifacts[first.package_artifact_id])
    assert package.package.name == "agent-meta-seed-harness"
    assert package.package.version == "0.1.0-dev.1"
    assert "agent_meta_seed_harness/probe.py" in files


def test_signature_does_not_validate_tampered_manifest():
    from cryptography.exceptions import InvalidSignature
    bundle = build()
    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    signature = bundle.artifacts[manifest["signature_artifact_id"]]
    manifest["package_version"] = "0.1.1"
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    with pytest.raises(InvalidSignature):
        key.public_key().verify(signature, manifest_signature_preimage(manifest))


def test_wrong_publisher_key_is_rejected_before_a_bundle_is_written():
    with pytest.raises(ValueError, match="does not match"):
        build(publisher_public_key=Ed25519PrivateKey.generate().public_key().public_bytes_raw())


def test_source_order_checkout_path_and_mtime_do_not_affect_package(tmp_path):
    source = tmp_path / "first"
    source.mkdir()
    (source / "probe.py").write_bytes(b"async def run():\n    return None\n")
    elsewhere = tmp_path / "elsewhere"
    shutil.copytree(source, elsewhere)
    first = build(files={"agent_meta_seed_harness/probe.py": (source / "probe.py").read_bytes(), "data.txt": b"data"})
    second = build(files={"data.txt": b"data", "agent_meta_seed_harness/probe.py": (elsewhere / "probe.py").read_bytes()})
    assert first == second


@pytest.mark.parametrize("path", ["../outside.py", "C:/outside.py", "a\\b", "/root.py", "CON.py", "a//b"])
def test_paths_fail_closed(path):
    with pytest.raises(AmpakError):
        build(files={path: b"no"})


def test_bundle_contains_no_private_key_and_write_is_content_addressed(tmp_path):
    bundle = build()
    bundle.write(tmp_path)
    bundle.write(tmp_path)
    assert not any(path.suffix in (".key", ".pem") for path in tmp_path.rglob("*"))
    marker = json.loads((tmp_path / "bundle.json").read_bytes())
    assert marker["manifest_artifact_id"] == bundle.manifest_artifact_id
    assert (tmp_path / "package.ampak").read_bytes() == bundle.artifacts[bundle.package_artifact_id]
    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    assert (tmp_path / "manifest.json").read_bytes() == bundle.artifacts[bundle.manifest_artifact_id]
    assert (tmp_path / "loop-policy.json").read_bytes() == bundle.artifacts[manifest["loop_policy_artifact_id"]]
    assert (tmp_path / "grant-requests.json").read_bytes() == bundle.artifacts[manifest["grant_requests_artifact_id"]]
    assert (tmp_path / "publisher.ed25519.pub").read_bytes() == Ed25519PrivateKey.from_private_bytes(bytes(range(32))).public_key().public_bytes_raw()
    assert len(list((tmp_path / "capabilities").glob("*.json"))) == 2
    ref = next(iter(bundle.artifacts))
    (tmp_path / "artifacts" / ref.rsplit("/", 1)[1]).write_bytes(b"wrong")
    with pytest.raises(ValueError, match="replace"):
        bundle.write(tmp_path)


KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))


def bundle(source=None, **overrides):
    project = Path(__file__).resolve().parents[2]
    source = source if source is not None else {name: files("agent_meta_seed_harness").joinpath(name.split("/", 1)[1]).read_bytes() for name in EXECUTION_SOURCE_PATHS}
    return build_bundle(files=source, dependency_lock=(project / "requirements-ci.lock").read_bytes(),
        publisher_public_key=KEY.public_key().public_bytes_raw(), signer=KEY,
        contract_bundle_sha256=sha256_hex((project / "docs/runtime-contract/manifest.json").read_bytes()), **overrides)


def changed(original, mutate, *, sign=True):
    artifacts = dict(original.artifacts)
    manifest = json.loads(artifacts[original.manifest_artifact_id])
    def add(value):
        raw = canonical_json(value) if not isinstance(value, bytes) else value
        reference = "artifact://sha256/" + sha256_hex(raw)
        artifacts[reference] = raw
        return reference
    mutate(manifest, artifacts, add)
    if sign:
        manifest["signature_artifact_id"] = add(KEY.sign(manifest_signature_preimage(manifest)))
    reference = add(manifest)
    return PackageBundle(reference, manifest["package_artifact_id"], artifacts)


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    root = tmp_path_factory.mktemp("package-public")
    with running_daemon(root, publishers=[sha256_hex(KEY.public_key().public_bytes_raw())]) as data_dir:
        yield data_dir, set(), root


def upload(runtime, package):
    data_dir, uploaded, root = runtime
    directory = root / "consumer-artifacts"
    directory.mkdir(exist_ok=True)
    for reference, raw in package.artifacts.items():
        if reference in uploaded:
            continue
        path = directory / reference.rsplit("/", 1)[1]
        path.write_bytes(raw)
        resource = admin(data_dir, "artifact", "put", str(path), "--kind", "code", "--media-type", "application/octet-stream")
        assert resource["artifact_id"] == reference
        uploaded.add(reference)


def validate(data_dir, reference):
    async def query():
        client = await connect(data_dir)
        try:
            before = await client.get_view()
            first = await client.validate_harness_package(reference)
            second = await client.validate_harness_package(reference)
            after = await client.get_view()
            assert first == second
            assert before["meta_revision"] == after["meta_revision"]
            assert before["fact_boundary_seq"] == after["fact_boundary_seq"]
            return first
        finally:
            await client.aclose()
    return asyncio.run(query())


NEGATIVE_CASES = json.loads((Path(__file__).resolve().parents[1] / "fixtures/package/negative-cases.json").read_bytes())


@pytest.mark.parametrize("case,expected", [(item["case"], item["expected"]) for item in NEGATIVE_CASES])
def test_runtime_public_package_validation_rejects_negative_inputs(runtime, case, expected):
    source = None
    if case.startswith("source_"):
        source = {"entry.py": b"def create():\n    raise RuntimeError('must not execute')\n", "unused.py": {
            "source_private": b"from agent_meta_runtime.adapters import store\n",
            "source_dynamic": b"from importlib import import_module as loader\nloader(module_name)\n",
            "source_path": b"import sys\npath = sys.path\npath.insert(0, 'checkout')\n"}[case]}
    package = bundle(source, **({"entrypoint": "entry:create"} if source else {}))
    def mutation(manifest, artifacts, add):
        if case == "unknown_field": manifest["preferred_backend"] = "anything"
        elif case == "bad_signature": manifest["signature_artifact_id"] = add(b"x" * 64)
        elif case == "contract": manifest["harness_contract_range"] = ">=9.0.0 <10.0.0"
        elif case == "backend_feature": manifest["required_backend_features"] = ["process"]
        elif case == "privileged_grant":
            grants = json.loads(artifacts[manifest["grant_requests_artifact_id"]])
            grants["requests"][0]["permission"] = "runtime.admin.stop"
            manifest["grant_requests_artifact_id"] = add(grants)
        elif case in {"foreign_realm", "foreign_capability"}:
            grants = json.loads(artifacts[manifest["grant_requests_artifact_id"]])
            if case == "foreign_realm": grants["requests"][0]["scope"]["realm_id"] = "realm://other"
            else: grants["requests"][0]["scope"]["targets"][0]["id"] = "capability://foreign"
            manifest["grant_requests_artifact_id"] = add(grants)
        elif case == "foreign_code":
            ref = manifest["capability_descriptor_artifact_ids"][0]
            descriptor = json.loads(artifacts[ref])
            descriptor["artifact_id"] = manifest["publisher_identity_artifact_id"]
            manifest["capability_descriptor_artifact_ids"] = sorted(add(descriptor) if item == ref else item for item in manifest["capability_descriptor_artifact_ids"])
        elif case == "provenance":
            provenance = json.loads(artifacts[manifest["build_provenance_artifact_id"]])
            provenance["source_files"] = {}
            manifest["build_provenance_artifact_id"] = add(provenance)
        elif case == "placement":
            ref = manifest["capability_descriptor_artifact_ids"][0]
            descriptor = json.loads(artifacts[ref])
            descriptor["placement"] = "unsupported-placement"
            manifest["capability_descriptor_artifact_ids"] = sorted(add(descriptor) if item == ref else item for item in manifest["capability_descriptor_artifact_ids"])
        elif case == "content_hash":
            raw = artifacts[manifest["package_artifact_id"]]
            # Whole-artifact hashing remains valid; AMPAK's internal file hash
            # is deliberately wrong and must be checked by ValidatePackage.
            manifest["package_artifact_id"] = add(raw[:-1] + bytes([raw[-1] ^ 1]))
    if not case.startswith("source_"):
        package = changed(package, mutation, sign=case != "bad_signature")
    upload(runtime, package)
    report = validate(runtime[0], package.manifest_artifact_id)
    assert not report["valid"] and any(issue.startswith(expected) for issue in report["issues"]), report


def test_validate_install_never_execute_entrypoint_and_name_version_history_is_not_reused(runtime):
    data_dir, _, root = runtime
    marker = root / "must-not-execute"
    source = {"entry.py": ("from pathlib import Path\n" + f"Path({str(marker)!r}).write_text('executed')\n" + "def create():\n    raise RuntimeError('must not execute')\n").encode()}
    package = bundle(source, entrypoint="entry:create", version="0.1.91")
    upload(runtime, package)
    report = validate(data_dir, package.manifest_artifact_id)
    assert report["valid"], report
    assert not marker.exists()
    manifest = json.loads(package.artifacts[package.manifest_artifact_id])
    def arguments(current):
        return ("harness", "install", "--name", manifest["package_name"], "--version", manifest["package_version"], current.manifest_artifact_id, current.package_artifact_id)
    installed = admin(data_dir, *arguments(package))
    equivalent = admin(data_dir, *arguments(package))
    assert installed["harness_id"] == equivalent["harness_id"]
    assert admin(data_dir, "harness", "inspect", installed["harness_id"])["status"] == "INSTALLED"
    assert not marker.exists()
    refs = admin(data_dir, "refs")
    assert refs["desired_revision"] == refs["serving_revision"] == refs["realized_revision"] == 0
    def different_policy(manifest, artifacts, add):
        policy = json.loads(artifacts[manifest["loop_policy_artifact_id"]])
        policy["max_turns"] = 4
        manifest["loop_policy_artifact_id"] = add(policy)
    incompatible = changed(package, different_policy)
    upload(runtime, incompatible)
    result, value = invoke(data_dir, *arguments(incompatible))
    assert result.returncode == 5 and value["error"]["code"] == "IDEMPOTENCY_CONFLICT", value
    assert value["error"]["details"]["package_name"] == manifest["package_name"]
    admin(data_dir, "harness", "uninstall", installed["harness_id"])
    result, value = invoke(data_dir, *arguments(package))
    assert result.returncode == 6 and value["error"]["code"] == "FAILED_PRECONDITION", value
    assert admin(data_dir, "harness", "inspect", installed["harness_id"])["status"] == "UNINSTALLED"
    assert not marker.exists()
