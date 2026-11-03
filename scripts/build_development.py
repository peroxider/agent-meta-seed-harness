"""Build offline development distributions plus hash-bound SBOM/provenance.

This command does not authorize a product release; build_release.py owns that
gate. No publisher credential is needed for a Python distribution build.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    # Bootstrap uses only stdlib before the Seed distribution is installed.
    # The installed evidence verifier independently checks this exact recipe.
    inputs, fixtures = {}, {}
    for directory in ("src", "tests", "scripts", "package", ".github", "docs/plans"):
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("build input escapes source snapshot")
            inputs[path.relative_to(root).as_posix()] = digest(path)
            if path.is_relative_to(root / "tests/fixtures"):
                fixtures[path.relative_to(root / "tests/fixtures").as_posix()] = digest(path)
    for name in ("pyproject.toml", "requirements-ci.in", "requirements-ci.lock", ".gitignore", "docs/release-policy.json"):
        inputs[name] = digest(root / name)
    encode = lambda values: hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"seed_source_sha256": encode(inputs), "fixture_sha256": encode(fixtures)}


def main():
    root = Path(__file__).resolve().parents[1]
    source = snapshot(root)
    subprocess.run([sys.executable, "-m", "build", "--no-isolation", str(root)], check=True)
    wheel = root / "dist/agent_meta_seed_harness-0.1.0.dev1-py3-none-any.whl"
    sdist = root / "dist/agent_meta_seed_harness-0.1.0.dev1.tar.gz"
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith(("tests/", "agent_meta_runtime/")) or name.endswith((".key", ".pem")):
                raise ValueError("forbidden content in Seed wheel")
    ci_inputs = json.loads((root / "docs/ci-inputs.json").read_text(encoding="utf-8"))
    components = [{"type": "library", "name": row["name"], "version": row["version"], "hashes": [{"alg": "SHA-256", "content": row["sha256"]}], "purl": f"pkg:pypi/{row['name'].lower().replace('_', '-')}@{row['version']}"} for row in ci_inputs["wheels"]]
    components.append({"type": "application", "name": "agent-meta-seed-harness", "version": "0.1.0.dev1", "hashes": [{"alg": "SHA-256", "content": digest(wheel)}]})
    sbom = {"bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1, "components": components}
    (root / "dist/sbom.cdx.json").write_text(json.dumps(sbom, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    if snapshot(root) != source:
        raise ValueError("source/fixtures changed during distribution build")
    provenance = {"schema": "seed-development-build/v1", "status": "DEVELOPMENT_NOT_RELEASED", **source,
        "artifacts": {wheel.name: digest(wheel), sdist.name: digest(sdist), "sbom.cdx.json": digest(root / "dist/sbom.cdx.json")}, "ci_inputs_sha256": digest(root / "docs/ci-inputs.json"), "lock_sha256": digest(root / "requirements-ci.lock"), "contract_bundle_sha256": digest(root / "docs/runtime-contract/manifest.json")}
    (root / "dist/development-provenance.json").write_text(json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Development artifacts built. Product release gates are evaluated separately.")


if __name__ == "__main__":
    main()
