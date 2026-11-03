"""Own an isolated full consumer run of an explicit, already signed bundle."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from agent_meta_seed_harness.evidence import (DEPENDENCIES, DEPENDENCY_REQUIREMENTS, PROFILES, REQUIREMENTS,
    digest, read_document, release_inputs, safe_path)
from agent_meta_seed_harness.packaging import load_bundle
from agent_meta_seed_harness.release_artifacts import verify_candidate_artifacts


SOURCE_PATHS = ["src", "tests", "scripts", "package", ".github", ".gitignore", "pyproject.toml", "requirements-ci.in",
    "requirements-ci.lock", "docs/release-policy.json", "docs/ci-inputs.json", "docs/runtime-contract"]


def git_identity(root):
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    top, head = git("rev-parse", "--show-toplevel"), git("rev-parse", "HEAD")
    if top.returncode or head.returncode or Path(top.stdout.strip()).resolve() != root:
        return None, False
    dirty = git("status", "--porcelain", "--untracked-files=all", "--", *SOURCE_PATHS)
    return head.stdout.strip(), dirty.returncode == 0 and not dirty.stdout.strip()


def release_context(root, publisher):
    commit, clean = git_identity(root)
    if not commit or not clean:
        raise ValueError("release evidence requires the committed, clean final source/input snapshot")
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_SHA") != commit:
        raise ValueError("release evidence requires its actual matching CI commit")
    repository, run_id = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_RUN_ID", "")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None or not run_id.isdecimal():
        raise ValueError("release evidence requires an identifiable CI run")
    if publisher not in read_document(root / "docs/release-policy.json")["approved_publishers"]:
        raise ValueError("supplied publisher is not approved by release policy")
    if os.name != "nt":
        raise ValueError("current non-Windows consumer uses INSECURE_TEST_ONLY; release evidence is unavailable")
    return {"seed_commit": commit, "repository": repository, "run_id": run_id,
        "run_url": f"https://github.com/{repository}/actions/runs/{run_id}"}


def reference(root, path):
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path, help="explicit signed bundle.json; no private signer is read")
    parser.add_argument("--label", required=True)
    parser.add_argument("--profile", choices=PROFILES, default="minimal")
    parser.add_argument("--kind", choices=("development", "release"), default="development")
    args = parser.parse_args()
    if re.fullmatch(r"[a-z0-9_-]+", args.label) is None:
        raise ValueError("run label must be a simple name")
    root = Path(__file__).resolve().parents[1]
    directory = safe_path(root, "reports/" + args.label)
    if directory.exists():
        raise ValueError("run label already exists; preserve its evidence and choose a new label")
    included = PROFILES[:PROFILES.index(args.profile) + 1]
    paths = tuple(dict.fromkeys(path for _name, (owner, proofs) in REQUIREMENTS.items() if owner in included for path in proofs))
    if any(not (root / path).is_file() for path in paths):
        raise ValueError("profile has missing required consumer proof modules")
    bundle = load_bundle(args.bundle)
    inputs = release_inputs(root)
    directory.mkdir(parents=True)
    bundle.write(directory / "input-package")
    refs = {"seed_wheel": reference(root, root / "dist/agent_meta_seed_harness-0.1.0.dev1-py3-none-any.whl"),
        "seed_sdist": reference(root, root / "dist/agent_meta_seed_harness-0.1.0.dev1.tar.gz"),
        "seed_sbom": reference(root, root / "dist/sbom.cdx.json"),
        "seed_provenance": reference(root, root / "dist/development-provenance.json"),
        "package_bundle": reference(root, directory / "input-package/bundle.json")}
    identities = verify_candidate_artifacts(root, refs, inputs=inputs)
    (directory / "input-artifacts.json").write_text(json.dumps(refs, sort_keys=True, indent=2) + "\n")
    ci = release_context(root, identities["publisher_key_sha256"]) if args.kind == "release" else None
    run_id = uuid.uuid4().hex
    command = [sys.executable, "-I", "-m", "pytest", "-q", "tests/unit", "tests/contract", "tests/acceptance",
        "--junitxml=" + str(directory / "junit.xml")]
    start = {"schema": "seed-consumer-run/v1", "status": "RUNNING", "run_id": run_id,
        "kind": args.kind, "profile": args.profile, "inputs": inputs, "identities": identities, "command": command, "ci": ci}
    (directory / "run.json").write_text(json.dumps(start, sort_keys=True, indent=2) + "\n")
    environment = dict(os.environ, PIP_NO_INDEX="1", PYTHONPATH="", PYTEST_ADDOPTS="",
        SEED_CONSUMER_BUNDLE=str(directory / "input-package/bundle.json"),
        SEED_CONSUMER_ARTIFACTS=str(directory / "input-artifacts.json"),
        SEED_CONSUMER_REPORT_DIR=directory.relative_to(root).as_posix(), SEED_CONSUMER_RUN_ID=run_id)
    try:
        result = subprocess.run(command, cwd=root, env=environment)
        if result.returncode:
            start.update(status="FAILED", returncode=result.returncode)
            (directory / "run.json").write_text(json.dumps(start, sort_keys=True, indent=2) + "\n")
            return result.returncode
        if release_inputs(root) != inputs:
            raise ValueError("source or pinned inputs changed during the owned run")
        observation = read_document(directory / "runtime-observation.json")
        if observation["run_id"] != run_id or any(observation[key] != identities[key] for key in (
                "package_artifact_id", "package_manifest_artifact_id", "publisher_key_sha256")):
            raise ValueError("Runtime observation does not belong to this exact bundle/run")
        subprocess.run([sys.executable, str(root / "scripts/record_development_evidence.py"), "--label", args.label],
            cwd=root, env=environment, check=True)
        env_path = directory / "environment.json"
        final = read_document(env_path)
        if any(final.get(key) != value for key, value in identities.items()):
            raise ValueError("full consumer run did not test the exact input artifacts")
        final.update(run_id=run_id, command=command, profile=args.profile)
        if args.kind == "release":
            if release_context(root, identities["publisher_key_sha256"]) != ci or final["credential_profile"] != "WINDOWS_DPAPI_CURRENT_USER":
                raise ValueError("CI source or protected credential observation changed")
            final.update(schema="seed-consumer-evidence/v1", status="VERIFIED", profile=args.profile,
                seed_commit=ci["seed_commit"], command=command, ci=ci, run_id=run_id,
                coverage_review="REQUIREMENT_AND_DEPENDENCY_STATUSES_NOT_PROMOTED")
        env_path.write_text(json.dumps(final, sort_keys=True, indent=2) + "\n")
        proof = {"junit": reference(root, directory / "junit.xml"), "environment": reference(root, env_path),
            "runtime_wheel": reference(root, root / "wheelhouse" / next(row["filename"] for row in
                    read_document(root / "docs/ci-inputs.json")["wheels"] if row["name"].lower().replace("_", "-") == "agent-meta-runtime")),
            "contract_bundle": reference(root, root / "docs/runtime-contract/manifest.json"), "artifacts": final["artifacts"],
            "test_hashes": {path: digest(root / path) for path in paths}}
        (directory / "proof.json").write_text(json.dumps(proof, sort_keys=True, indent=2) + "\n")
        index = {"schema": "seed-consumer-coverage-index/v1", "status": "PENDING_COVERAGE_REVIEW", "profile": args.profile,
            "proof": reference(root, directory / "proof.json"),
            "requirements": {name: list(proofs) for name, (owner, proofs) in REQUIREMENTS.items() if owner in included},
            "dependencies": {name: list(DEPENDENCY_REQUIREMENTS[name]) for owner in included for name in DEPENDENCIES[owner]}}
        (directory / "coverage-index.json").write_text(json.dumps(index, sort_keys=True, indent=2) + "\n")
        start.update(status="PASSED", environment=reference(root, env_path), coverage_review="PENDING")
        (directory / "run.json").write_text(json.dumps(start, sort_keys=True, indent=2) + "\n")
        print(f"Consumer run {args.label}: PASSED; {final['status']}; requirement/dependency ledger unchanged")
        return 0
    except BaseException as error:
        start.update(status="INVALID_EVIDENCE", error_type=type(error).__name__)
        (directory / "run.json").write_text(json.dumps(start, sort_keys=True, indent=2) + "\n")
        raise



if __name__ == "__main__":
    raise SystemExit(main())
