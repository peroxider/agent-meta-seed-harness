"""SH-REL-02: actual offline distributions + signed AMPAK input binding.

These are development consumer proofs, not synthetic reports promoted into a
release verdict. Runtime lifecycle/AC-M17 proofs remain separate requirements.
"""

import copy
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.evidence import check_traceability, digest, release_inputs, safe_path, read_document
from agent_meta_seed_harness.packaging import PackageBundle
from agent_meta_seed_harness.release_artifacts import verify_candidate_artifacts
from seed_package import seed_bundle


ROOT = Path(__file__).resolve().parents[2]


def reference(root, path):
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(path)}


@pytest.fixture(scope="module")
def candidate(tmp_path_factory):
    root = tmp_path_factory.mktemp("relocated-final-candidate")
    for name in ("src", "tests", "scripts", "docs", "package", ".github"):
        shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("pyproject.toml", "requirements-ci.in", "requirements-ci.lock", "README.md", "CHANGELOG.md", "LICENSE", ".gitattributes", ".gitignore"):
        shutil.copyfile(ROOT / name, root / name)
    # Copy only explicitly declared binary inputs, with hashes checked below.
    (root / "wheelhouse").mkdir()
    ci = json.loads((ROOT / "docs/ci-inputs.json").read_bytes())
    for row in ci["wheels"]:
        source = ROOT / "wheelhouse" / row["filename"]
        assert digest(source) == row["sha256"]
        shutil.copyfile(source, root / "wheelhouse" / row["filename"])
    inputs = release_inputs(root)
    supplied = os.environ.get("SEED_CONSUMER_ARTIFACTS")
    if supplied:
        sealed = read_document(Path(supplied))
        verify_candidate_artifacts(ROOT, sealed, inputs=release_inputs(ROOT))
        (root / "dist").mkdir()
        for key in ("seed_wheel", "seed_sdist", "seed_sbom", "seed_provenance"):
            path = safe_path(ROOT, sealed[key]["path"])
            shutil.copyfile(path, root / "dist" / path.name)
    else:
        result = subprocess.run([sys.executable, "-I", str(root / "scripts/build_development.py")], cwd=root,
            env=dict(os.environ, PIP_NO_INDEX="1", PYTHONPATH="", PYTHONNOUSERSITE="1"),
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
    bundle, _publisher = seed_bundle()
    bundle.write(root / "candidate-package")
    refs = {"seed_wheel": reference(root, root / "dist/agent_meta_seed_harness-0.1.0.dev1-py3-none-any.whl"),
        "seed_sdist": reference(root, root / "dist/agent_meta_seed_harness-0.1.0.dev1.tar.gz"),
        "seed_sbom": reference(root, root / "dist/sbom.cdx.json"),
        "seed_provenance": reference(root, root / "dist/development-provenance.json"),
        "package_bundle": reference(root, root / "candidate-package/bundle.json")}
    return root, inputs, refs, bundle


def test_final_installed_wheel_sdist_sbom_and_signed_ampak_bind_same_inputs(candidate):
    root, inputs, refs, bundle = candidate
    identities = verify_candidate_artifacts(root, refs, inputs=inputs)
    assert identities["package_manifest_artifact_id"] == bundle.manifest_artifact_id
    assert identities["package_artifact_id"] == bundle.package_artifact_id
    assert identities["seed_wheel_sha256"] == digest(ROOT / "dist/agent_meta_seed_harness-0.1.0.dev1-py3-none-any.whl")
    installed = metadata.distribution("agent-meta-seed-harness")
    assert not json.loads(installed.read_text("direct_url.json") or "{}").get("dir_info", {}).get("editable", False)
    with zipfile.ZipFile(root / refs["seed_wheel"]["path"]) as archive:
        for name in archive.namelist():
            if name.startswith("agent_meta_seed_harness/") and not name.endswith("/"):
                assert archive.read(name) == installed.locate_file(name).read_bytes(), name
    assert (root / "candidate-package/package.ampak").read_bytes() == bundle.artifacts[bundle.package_artifact_id]
    assert release_inputs(root) == inputs  # build did not mutate input/source
    # Persist the actual tested bytes, not a rebuilt approximation. This public
    # fixture signer is explicitly DEVELOPMENT_ONLY, never a release signer.
    directory = safe_path(ROOT, os.environ.get("SEED_CONSUMER_REPORT_DIR", "reports/bootstrap"))
    destination = directory / "candidate"
    destination.mkdir(parents=True, exist_ok=True)
    copied = {}
    for key in ("seed_wheel", "seed_sdist", "seed_sbom", "seed_provenance"):
        path = root / refs[key]["path"]
        shutil.copyfile(path, destination / path.name)
        copied[key] = reference(ROOT, destination / path.name)
    shutil.copytree(root / "candidate-package", destination / "package", dirs_exist_ok=True)
    copied["package_bundle"] = reference(ROOT, destination / "package/bundle.json")
    assert verify_candidate_artifacts(ROOT, copied, inputs=release_inputs(ROOT)) == identities
    (destination / "verification.json").write_bytes(canonical_json({"schema": "seed-tested-candidate/v1",
        "status": "DEVELOPMENT_ONLY", "inputs": inputs, "artifacts": copied, "identities": identities}))


@pytest.mark.parametrize("mutation", ["wheel", "source", "sbom", "provenance", "signature", "package_code", "package_lock", "closure", "review_copy"])
def test_self_hashed_stale_or_inconsistent_artifacts_are_rejected(candidate, tmp_path, mutation):
    original, inputs, refs, bundle = candidate
    root = tmp_path / "changed-candidate"
    shutil.copytree(original, root, ignore=shutil.ignore_patterns("wheelhouse", "__pycache__", "*.pyc"))
    refs = copy.deepcopy(refs)
    def update(key, value):
        path = root / refs[key]["path"]
        path.write_bytes(value)
        refs[key] = reference(root, path)
    if mutation == "wheel":
        update("seed_wheel", b"not a wheel")
    elif mutation == "source":
        path = root / "src/agent_meta_seed_harness/loop.py"
        path.write_bytes(path.read_bytes() + b"\n# post-proof source change\n")
    elif mutation in ("sbom", "provenance"):
        provenance = json.loads((root / refs["seed_provenance"]["path"]).read_bytes())
        if mutation == "sbom":
            sbom = json.loads((root / refs["seed_sbom"]["path"]).read_bytes())
            sbom["components"][0]["hashes"][0]["content"] = "0" * 64
            update("seed_sbom", canonical_json(sbom))
            provenance["artifacts"]["sbom.cdx.json"] = refs["seed_sbom"]["sha256"]
        else:
            provenance["contract_bundle_sha256"] = "0" * 64
        update("seed_provenance", canonical_json(provenance))
    elif mutation == "signature":
        artifacts = dict(bundle.artifacts)
        manifest = json.loads(artifacts.pop(bundle.manifest_artifact_id))
        signature = b"\0" * 64
        ref = "artifact://sha256/" + sha256_hex(signature)
        artifacts[ref] = signature
        manifest["signature_artifact_id"] = ref
        raw = canonical_json(manifest)
        manifest_ref = "artifact://sha256/" + sha256_hex(raw)
        artifacts[manifest_ref] = raw
        PackageBundle(manifest_ref, bundle.package_artifact_id, artifacts).write(root / "broken-package")
        refs["package_bundle"] = reference(root, root / "broken-package/bundle.json")
    elif mutation in ("package_code", "package_lock"):
        if mutation == "package_code":
            source = (ROOT / "src/agent_meta_seed_harness/loop.py").read_bytes() + b"\n# different signed code\n"
            changed, _ = seed_bundle(overrides={"agent_meta_seed_harness/loop.py": source})
        else:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from agent_meta_seed_harness.packaging import EXECUTION_SOURCE_PATHS, build_bundle
            key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
            changed = build_bundle(files={n: (ROOT / "src" / n).read_bytes() for n in EXECUTION_SOURCE_PATHS},
                dependency_lock=b"different locked dependencies\n", publisher_public_key=key.public_key().public_bytes_raw(), signer=key,
                contract_bundle_sha256=inputs["contract_sha256"])
        changed.write(root / "broken-package")
        refs["package_bundle"] = reference(root, root / "broken-package/bundle.json")
    elif mutation == "review_copy":
        (root / "candidate-package/package.ampak").write_bytes(b"different human-facing package")
    else:
        marker = json.loads((root / refs["package_bundle"]["path"]).read_bytes())
        manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        marker["artifact_ids"].remove(manifest["capability_descriptor_artifact_ids"][0])
        update("package_bundle", canonical_json(marker))
    with pytest.raises(ValueError):
        verify_candidate_artifacts(root, refs, inputs=inputs)


def test_release_gate_rejects_unverified_copy_without_preventing_future_verification(tmp_path):
    original = (ROOT / "docs/traceability.json").read_bytes()
    ledger = json.loads(original)
    row = next(row for row in ledger["requirements"] if row["id"] == "SH-REL-02")
    row.update(status="IN_PROGRESS", evidence=None)
    path = tmp_path / "unverified-copy.json"
    path.write_bytes(canonical_json(ledger))
    issues = check_traceability(ROOT, "minimal", manifest_path=path)
    assert "SH-REL-02: not VERIFIED" in issues
    assert (ROOT / "docs/traceability.json").read_bytes() == original
