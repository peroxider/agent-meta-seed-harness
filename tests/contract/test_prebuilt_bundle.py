"""Explicit signed artifact input; never silently rebuild an invalid bundle."""

from importlib.resources import files
import json
from pathlib import Path
import runpy

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.packaging import (EXECUTION_SOURCE_PATHS, PackageBundle, build_bundle,
    load_bundle, require_bundle_inputs)
from seed_package import seed_bundle


ROOT = Path(__file__).resolve().parents[2]


def supplied(tmp_path):
    source = {n: files("agent_meta_seed_harness").joinpath(n.split("/", 1)[1]).read_bytes() for n in EXECUTION_SOURCE_PATHS}
    key = Ed25519PrivateKey.generate()  # independent fixture signer, not the public fallback key
    bundle = build_bundle(files=source, dependency_lock=(ROOT / "requirements-ci.lock").read_bytes(),
        publisher_public_key=key.public_key().public_bytes_raw(), signer=key,
        contract_bundle_sha256=sha256_hex((ROOT / "docs/runtime-contract/manifest.json").read_bytes()))
    bundle.write(tmp_path)
    return source, bundle, key


def test_supplied_bundle_retains_exact_signature_publisher_and_inputs(tmp_path, monkeypatch):
    source, bundle, key = supplied(tmp_path)
    path = tmp_path / "bundle.json"
    loaded = load_bundle(path)
    assert loaded == bundle
    require_bundle_inputs(loaded, files=source, dependency_lock=(ROOT / "requirements-ci.lock").read_bytes(),
        contract_bundle_sha256=sha256_hex((ROOT / "docs/runtime-contract/manifest.json").read_bytes()))
    monkeypatch.setenv("SEED_CONSUMER_BUNDLE", str(path))
    actual, publisher = seed_bundle()
    assert actual == bundle and publisher == sha256_hex(key.public_key().public_bytes_raw())
    # Custom negative fixtures keep their explicit source and test publisher.
    changed, other = seed_bundle(overrides={"agent_meta_seed_harness/loop.py": source["agent_meta_seed_harness/loop.py"] + b"\n# fixture\n"})
    assert changed != bundle and other != publisher


@pytest.mark.parametrize("mutation", ["marker", "hash", "signature", "closure", "missing", "source", "lock", "contract"])
def test_bad_prebuilt_input_cannot_fall_back_to_a_new_test_package(tmp_path, monkeypatch, mutation):
    source, bundle, _key = supplied(tmp_path)
    marker = tmp_path / "bundle.json"
    if mutation == "marker":
        marker.write_bytes(b'{"schema":"wrong","schema":"seed-package-bundle/v1"}')
    elif mutation == "hash":
        path = tmp_path / "artifacts" / bundle.package_artifact_id.rsplit("/", 1)[1]
        path.write_bytes(path.read_bytes() + b"changed")
    elif mutation in ("signature", "closure"):
        artifacts = dict(bundle.artifacts)
        manifest = json.loads(artifacts[bundle.manifest_artifact_id])
        if mutation == "signature":
            signature = b"\0" * 64
            ref = "artifact://sha256/" + sha256_hex(signature)
            artifacts[ref] = signature
            manifest["signature_artifact_id"] = ref
            raw = canonical_json(manifest)
            manifest_id = "artifact://sha256/" + sha256_hex(raw)
            artifacts[manifest_id] = raw
            PackageBundle(manifest_id, bundle.package_artifact_id, artifacts).write(tmp_path / "changed")
            marker = tmp_path / "changed/bundle.json"
        else:
            data = json.loads(marker.read_bytes())
            data["artifact_ids"].remove(manifest["capability_descriptor_artifact_ids"][0])
            marker.write_bytes(canonical_json(data))
    elif mutation == "missing":
        marker = tmp_path / "missing/bundle.json"
    else:
        kwargs = {"files": source, "dependency_lock": (ROOT / "requirements-ci.lock").read_bytes(),
            "contract_bundle_sha256": sha256_hex((ROOT / "docs/runtime-contract/manifest.json").read_bytes())}
        if mutation == "source":
            kwargs["files"] = {**source, "agent_meta_seed_harness/loop.py": b"different code"}
        elif mutation == "lock":
            kwargs["dependency_lock"] = b"different lock"
        else:
            kwargs["contract_bundle_sha256"] = "0" * 64
        with pytest.raises(ValueError):
            require_bundle_inputs(load_bundle(marker), **kwargs)
        return
    monkeypatch.setenv("SEED_CONSUMER_BUNDLE", str(marker))
    with pytest.raises((ValueError, OSError)):
        seed_bundle()


def test_release_run_preflight_refuses_uncommitted_or_non_ci_source(tmp_path):
    api = runpy.run_path(str(ROOT / "scripts/run_consumer.py"))
    assert api["git_identity"](tmp_path) == (None, False)
    with pytest.raises(ValueError, match="committed, clean"):
        api["release_context"](tmp_path, "0" * 64)
