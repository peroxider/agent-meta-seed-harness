"""Record bounded development evidence without promoting release statuses."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from agent_meta_seed_harness.evidence import release_inputs, read_document
from agent_meta_seed_harness.release_artifacts import verify_candidate_artifacts


def collection_identities(output):
    identities = set()
    for line in output.splitlines():
        if not line.startswith("tests/") or "::" not in line:
            continue
        module, _, rest = line.partition("::")
        body, bracket, parameters = rest.partition("[")
        parts = body.split("::")
        classname = module.removesuffix(".py").replace("/", ".")
        if len(parts) > 1:
            classname += "." + ".".join(parts[:-1])
        identities.add((classname, parts[-1] + bracket + parameters))
    return identities


def require_full_collection(root, cases):
    result = subprocess.run([sys.executable, "-I", "-m", "pytest", "--collect-only", "-q", "tests/unit", "tests/contract", "tests/acceptance"],
        cwd=root, env=dict(os.environ, PYTEST_ADDOPTS="", PYTHONPATH="", PIP_NO_INDEX="1"),
        capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise ValueError("cannot verify current development test collection")
    expected = collection_identities(result.stdout)
    actual = {(case.get("classname"), case.get("name")) for case in cases}
    if not expected or expected != actual or len(actual) != len(cases):
        raise ValueError("JUnit is not the complete current development collection")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not re.fullmatch("[a-z0-9_-]+", args.label):
        raise ValueError("evidence label must be a simple name")
    root = Path(__file__).resolve().parents[1]
    directory = root / "reports" / args.label
    (directory / "environment.json").unlink(missing_ok=True)
    junit = directory / "junit.xml"
    cases = list(ET.parse(junit).iter("testcase"))
    if not cases:
        raise ValueError("refusing to record a zero-test run")
    require_full_collection(root, cases)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    counts = {"collected": len(cases), "failed": 0, "errors": 0, "skipped": 0, "passed": 0}
    for case in cases:
        if case.find("failure") is not None:
            counts["failed"] += 1
        elif case.find("error") is not None:
            counts["errors"] += 1
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    ci = json.loads((root / "docs/ci-inputs.json").read_text(encoding="utf-8"))
    inputs = release_inputs(root)
    execution_profiles = set()
    for case in cases:
        module, name = case.get("classname", ""), case.get("name", "")
        if module == "tests.acceptance.test_ac_m17":
            execution_profiles.add("in_memory")
        if module in ("tests.contract.test_host_recovery", "tests.contract.test_loop_recovery", "tests.contract.test_tool_dispatch"):
            for profile in ("in_memory", "trusted_in_process"):
                if "[" + profile in name:
                    execution_profiles.add(profile)
    candidate_path = directory / "candidate/verification.json"
    candidate = read_document(candidate_path)
    if candidate.get("schema") != "seed-tested-candidate/v1" or candidate.get("status") != "DEVELOPMENT_ONLY" or candidate.get("inputs") != inputs:
        raise ValueError("tested candidate differs from final development inputs")
    identities = verify_candidate_artifacts(root, candidate["artifacts"], inputs=inputs)
    if candidate.get("identities") != identities:
        raise ValueError("tested candidate identities changed")
    observation_path = directory / "runtime-observation.json"
    observation = read_document(observation_path)
    if observation.get("schema") != "seed-runtime-observation/v1" or any(observation.get(field) != identities[field]
        for field in ("package_artifact_id", "package_manifest_artifact_id", "publisher_key_sha256")):
        raise ValueError("actual Runtime observation differs from tested candidate")
    record = {
        "schema": "seed-development-evidence/v1", "status": "DEVELOPMENT_ONLY",
        **inputs, **identities, "artifacts": candidate["artifacts"],
        "seed_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "runtime_wheel_sha256": ci["runtime_wheel_sha256"],
        "contract_sha256": hashlib.sha256((root / "docs/runtime-contract/manifest.json").read_bytes()).hexdigest(),
        "python": platform.python_version(), "os": platform.system(),
        "backend": "+".join(sorted(execution_profiles)) + "/offline-development-not-isolation-proof",
        "execution_profiles": sorted(execution_profiles),
        "credential_profile": observation["credential_profile"], "contracts": observation["contracts"],
        "runtime_observation": {"path": observation_path.relative_to(root).as_posix(), "sha256": hashlib.sha256(observation_path.read_bytes()).hexdigest()},
        "command": ["python", "-I", "-m", "pytest", "-q", "tests/unit", "tests/contract", "tests/acceptance", f"--junitxml=reports/{args.label}/junit.xml"],
        "junit_sha256": hashlib.sha256(junit.read_bytes()).hexdigest(), **counts,
    }
    (directory / "environment.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.label}: {counts['passed']}/{counts['collected']} passed; development evidence only")
    return bool(counts["failed"] or counts["errors"] or counts["skipped"])


if __name__ == "__main__":
    raise SystemExit(main())
