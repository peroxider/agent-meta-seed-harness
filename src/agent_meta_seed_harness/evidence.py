"""Seed release evidence checks. Missing or unrun requirements always fail."""

from __future__ import annotations

import hashlib
import json
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
import re
import tomllib
import zipfile
import zlib
import xml.etree.ElementTree as ET

PROFILES = ("minimal", "provider", "tools", "session", "evolution")
REQUIREMENTS = {
    "SH-BOOT-01": ("minimal", ("tests/contract/test_project_boundary.py",)),
    "SH-PKG-01": ("minimal", ("tests/contract/test_package_contract.py",)),
    "SH-HOST-01": ("minimal", ("tests/contract/test_public_imports.py", "tests/contract/test_host_contract.py")),
    "SH-HOST-02": ("minimal", ("tests/acceptance/test_host_bootstrap.py",)),
    "SH-LOOP-01": ("minimal", ("tests/contract/test_loop_semantics.py",)),
    "SH-CTX-01": ("minimal", ("tests/contract/test_context_projection.py",)),
    "SH-TOOL-01": ("minimal", ("tests/contract/test_tool_dispatch.py",)),
    "SH-REC-01": ("minimal", ("tests/contract/test_host_recovery.py", "tests/contract/test_loop_recovery.py")),
    "SH-REL-01": ("minimal", ("tests/acceptance/test_release_lifecycle.py",)),
    "SH-REL-02": ("minimal", ("tests/contract/test_release_evidence.py",)),
    "NFR-M48": ("minimal", ("tests/contract/test_nfr_m48.py",)),
    "AC-M17": ("minimal", ("tests/acceptance/test_ac_m17.py",)),
    "AC-M48": ("minimal", ("tests/acceptance/test_ac_m48.py",)),
    "SH-PROV-01": ("provider", ("tests/contract/test_provider_contract.py", "tests/contract/test_provider_package.py", "tests/contract/test_provider_host_binding.py")),
    "SH-PROV-02": ("provider", ("tests/contract/test_provider_security.py", "tests/contract/test_provider_replay.py", "tests/contract/test_provider_recovery.py")),
    "SH-PROV-03": ("provider", ("tests/acceptance/test_live_provider.py",)),
    "SH-CAP-01": ("tools", ("tests/contract/test_capability_toolset.py",)),
    "SH-CAP-02": ("tools", ("tests/acceptance/test_capability_toolset.py", "tests/acceptance/test_scratch_tools.py", "tests/acceptance/test_scratch_recovery.py", "tests/acceptance/test_scratch_retirement.py", "tests/acceptance/test_scratch_backup.py")),
    "SH-SESS-01": ("session", ("tests/contract/test_session_consistency.py",)),
    "SH-SESS-02": ("session", ("tests/acceptance/test_session_recovery.py",)),
    "SH-EVO-01": ("evolution", ("tests/acceptance/test_evolution_pipeline.py",)),
    "SH-EVO-02": ("evolution", ("tests/contract/test_evolution_policy.py",)),
    "SH-GOV-01": ("evolution", ("tests/contract/test_evolution_governance.py",)),
    "SH-GOV-02": ("evolution", ("tests/acceptance/test_evolution_release.py",)),
}
DEPENDENCIES = {"minimal": ("RP-00", "RP-01", "RP-02"), "provider": ("RP-03",), "tools": ("RP-04",), "session": ("RP-05",), "evolution": ("RP-06", "RP-07")}

# Required consumer modules, not a claim that file collection proves an entire
# Runtime dependency. The actual assertions and reviewed CI verdict still own
# that claim. Every dependency must carry its own hash-bound consumer report.
DEPENDENCY_REQUIREMENTS = {
    "RP-00": ("SH-BOOT-01", "SH-PKG-01", "SH-HOST-02", "SH-REL-01"),
    "RP-01": ("SH-HOST-01", "SH-HOST-02", "SH-CTX-01", "SH-LOOP-01", "SH-TOOL-01", "AC-M17", "AC-M48", "NFR-M48"),
    "RP-02": ("SH-REC-01", "AC-M17"),
    "RP-03": ("SH-PROV-01", "SH-PROV-02", "SH-PROV-03"),
    "RP-04": ("SH-CAP-01", "SH-CAP-02"),
    "RP-05": ("SH-SESS-01", "SH-SESS-02"),
    "RP-06": ("SH-EVO-01", "SH-EVO-02"),
    "RP-07": ("SH-GOV-01", "SH-GOV-02", "SH-EVO-01"),
}
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_JUNIT_BYTES = 32 * 1024 * 1024


def _hash(value):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("invalid SHA-256")
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def read_document(path):
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("evidence document exceeds byte ceiling")
    def invalid_constant(value):
        raise ValueError("non-finite JSON number")
    value = json.loads(path.read_bytes(), object_pairs_hook=_pairs, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("evidence document must be an object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(root: Path) -> str:
    """Bind reports to executable/source/policy/lock inputs, never reports."""
    inputs = {}
    for name in ("src", "tests", "scripts", "package", ".github"):
        for path in sorted((root / name).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"):
                if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError("source input escapes checkout")
                inputs[path.relative_to(root).as_posix()] = digest(path)
    for name in ("pyproject.toml", "requirements-ci.in", "requirements-ci.lock", ".gitignore", "docs/release-policy.json"):
        path = root / name
        if path.is_file():
            inputs[name] = digest(path)
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fixture_digest(root: Path) -> str:
    directory = root / "tests/fixtures"
    inputs = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("fixture input escapes checkout")
        inputs[path.relative_to(directory).as_posix()] = digest(path)
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def safe_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or "\\" in value or ":" in value:
        raise ValueError("evidence path must be relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")) or not value:
        raise ValueError("evidence path escapes root")
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("evidence symlink escapes root")
    return resolved


def _verified_file(root: Path, item: dict) -> Path:
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise ValueError("invalid evidence reference")
    _hash(item["sha256"])
    path = safe_path(root, item["path"])
    if digest(path) != item["sha256"]:
        raise ValueError("evidence hash mismatch")
    return path


def release_inputs(root: Path) -> dict:
    """Verify explicit local wheel/contract/lock inputs; never discover a repo."""
    ci = read_document(root / "docs/ci-inputs.json")
    contract_path = root / "docs/runtime-contract/manifest.json"
    contract = read_document(contract_path)
    if ci.get("schema") != "seed-ci-inputs/v1" or contract.get("schema") != "seed-runtime-contract-bundle/v1":
        raise ValueError("unsupported pinned input schema")
    wheels = ci["wheels"]
    if not isinstance(wheels, list) or not all(isinstance(row, dict) and isinstance(row.get("name"), str) for row in wheels):
        raise ValueError("invalid pinned wheels")
    lock = root / "requirements-ci.lock"
    locked = [line for line in lock.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    expected_lock = []
    for row in wheels:
        name, version, filename = row["name"].lower().replace("_", "-").replace(".", "-"), row["version"], row["filename"]
        if not isinstance(version, str) or not isinstance(filename, str) or "/" in filename or "\\" in filename or not filename.endswith(".whl"):
            raise ValueError("pinned dependency must name a binary wheel")
        _verified_file(root, {"path": "wheelhouse/" + filename, "sha256": row["sha256"]})
        expected_lock.append(f"{name}=={version} --hash=sha256:{row['sha256']}")
    if len(expected_lock) != len(set(line.split("==")[0] for line in expected_lock)) or sorted(locked) != sorted(expected_lock):
        raise ValueError("wheelhouse inputs differ from exact dependency lock")
    runtime = [row for row in wheels if row.get("name", "").lower().replace("_", "-") == "agent-meta-runtime"]
    if len(runtime) != 1:
        raise ValueError("exactly one Runtime wheel input required")
    runtime = runtime[0]
    filename = runtime["filename"]
    if not isinstance(filename, str) or "/" in filename or "\\" in filename or not filename.endswith(".whl"):
        raise ValueError("Runtime input must name a wheel file")
    wheel = _verified_file(root, {"path": "wheelhouse/" + filename, "sha256": runtime["sha256"]})
    if ci["runtime_wheel_sha256"] != runtime["sha256"] or contract["runtime_wheel_sha256"] != runtime["sha256"]:
        raise ValueError("pinned Runtime wheel/contract inputs disagree")
    try:
        with zipfile.ZipFile(wheel) as archive:
            metadata = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            if len(metadata) != 1 or archive.getinfo(metadata[0]).file_size > 1024 * 1024:
                raise ValueError("Runtime wheel METADATA missing or ambiguous")
            identity = BytesParser().parsebytes(archive.read(metadata[0]))
            if identity["Name"] != "agent-meta-runtime" or identity["Version"] != runtime["version"] or identity["Version"] != contract["runtime_version"]:
                raise ValueError("Runtime wheel identity differs from pinned contract")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error):
        raise ValueError("Runtime input is not a wheel archive") from None
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = [v for v in project["project"]["dependencies"] if v.startswith("agent-meta-runtime")]
    if dependencies != ["agent-meta-runtime==" + runtime["version"]]:
        raise ValueError("project does not pin the same Runtime version")
    runtime_lines = [line for line in lock.read_text(encoding="utf-8").splitlines() if line.startswith("agent-meta-runtime")]
    if runtime_lines != [f"agent-meta-runtime=={runtime['version']} --hash=sha256:{runtime['sha256']}"]:
        raise ValueError("Runtime wheel differs from exact hash lock")
    files = contract["files"]
    if not isinstance(files, list) or not files or not all(isinstance(row, dict) for row in files):
        raise ValueError("empty or invalid contract inputs")
    paths = [row["path"] for row in files]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate contract input paths")
    for row in files:
        _verified_file(root, {"path": "docs/runtime-contract/" + row["path"], "sha256": row["sha256"]})
    policy = read_document(root / "docs/release-policy.json")
    approved = policy.get("approved_publishers")
    if policy.get("schema") != "seed-release-policy/v1" or not isinstance(approved, list) or not all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) for v in approved) or approved != sorted(set(approved)):
        raise ValueError("invalid reviewed release publisher policy")
    return {"runtime_wheel_sha256": runtime["sha256"], "contract_sha256": digest(contract_path),
        "lock_sha256": digest(lock), "seed_source_sha256": source_digest(root), "fixture_sha256": fixture_digest(root),
        "release_policy_sha256": digest(root / "docs/release-policy.json"),
        "runtime_version": runtime["version"], "harness_contract_version": contract["harness_contract_version"],
        "os": ci["os"], "python": ci["python"], "architecture": ci["architecture"]}


def _consumer_proof(root, proof, paths, *, inputs, profile, artifact_cache=None):
    if not isinstance(proof, dict):
        raise ValueError("no consumer evidence")
    junit = _verified_file(root, proof["junit"])
    env = read_document(_verified_file(root, proof["environment"]))
    if env.get("schema") != "seed-consumer-evidence/v1" or env.get("status") != "VERIFIED":
        raise ValueError("release requires verified consumer evidence, not a development report")
    if env.get("profile") not in PROFILES or PROFILES.index(env["profile"]) < PROFILES.index(profile):
        raise ValueError("consumer profile does not cover requirement")
    if not isinstance(env.get("seed_commit"), str) or re.fullmatch("(?:[0-9a-f]{40}|[0-9a-f]{64})", env["seed_commit"]) is None:
        raise ValueError("missing full Seed commit")
    for field, value in inputs.items():
        if env.get(field) != value:
            raise ValueError(f"{field} differs from final pinned inputs")
    for field, key in (("runtime_wheel_sha256", "runtime_wheel"), ("contract_sha256", "contract_bundle")):
        if digest(_verified_file(root, proof[key])) != inputs[field]:
            raise ValueError(f"{key} differs from final pinned inputs")
    if env.get("junit_sha256") != digest(junit):
        raise ValueError("JUnit differs from environment")
    from .release_artifacts import verify_candidate_artifacts
    cache_key = json.dumps(proof["artifacts"], sort_keys=True)
    if artifact_cache is not None and cache_key in artifact_cache:
        artifacts = artifact_cache[cache_key]
    else:
        artifacts = verify_candidate_artifacts(root, proof["artifacts"], inputs=inputs)
        if artifact_cache is not None:
            artifact_cache[cache_key] = artifacts
    if any(env.get(field) != value for field, value in artifacts.items()):
        raise ValueError("consumer artifacts differ from final wheel/AMPAK inputs")
    if artifacts["publisher_key_sha256"] not in read_document(root / "docs/release-policy.json")["approved_publishers"]:
        raise ValueError("candidate publisher is not approved by release policy")
    command = env.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command) or not {"-I", "-m", "pytest"} <= set(command):
        raise ValueError("missing isolated consumer command")
    profiles = env.get("execution_profiles")
    if not isinstance(profiles, list) or not profiles or not all(isinstance(v, str) and v for v in profiles) or profiles != sorted(set(profiles)) or "in_memory" not in profiles:
        raise ValueError("missing actual InMemory execution profile")
    credential = env.get("credential_profile")
    if credential not in ("WINDOWS_DPAPI_CURRENT_USER", "OS_PROTECTED"):
        raise ValueError("product evidence requires a protected credential profile")
    if inputs["os"] == "Windows" and credential != "WINDOWS_DPAPI_CURRENT_USER":
        raise ValueError("Windows product evidence requires its DPAPI credential profile")
    contracts = env.get("contracts")
    if not isinstance(contracts, dict) or contracts.get("harness") != inputs["harness_contract_version"] or contracts.get("artifact_format") != "AMPAK1" or not isinstance(contracts.get("public_api"), str) or re.fullmatch(r"1\.[0-9]+", contracts["public_api"]) is None or not isinstance(contracts.get("capability"), str) or re.fullmatch(r"1\.[0-9]+\.[0-9]+", contracts["capability"]) is None:
        raise ValueError("missing contract/protocol versions")
    if junit.stat().st_size > MAX_JUNIT_BYTES:
        raise ValueError("JUnit exceeds byte ceiling")
    tree = ET.parse(junit)
    cases = list(tree.iter("testcase"))
    if not cases or any(not c.get("classname") or not c.get("name") for c in cases):
        raise ValueError("zero or unidentified tests")
    if any(any(c.find(tag) is not None for tag in ("failure", "error", "skipped")) for c in cases):
        raise ValueError("evidence run contains failure/skip/xfail")
    if len({(c.get("classname"), c.get("name")) for c in cases}) != len(cases):
        raise ValueError("duplicate collected test identities")
    for suite in (node for node in tree.iter() if node.tag in ("testsuite", "testsuites")):
        if any(int(suite.get(key, "0")) != 0 for key in ("failures", "errors", "skipped")):
            raise ValueError("JUnit suite reports failure/error/skip")
    hashes = proof["test_hashes"]
    if not isinstance(hashes, dict):
        raise ValueError("missing named test hashes")
    for path in paths:
        module = path.removesuffix(".py").replace("/", ".")
        if not any(c.get("classname") == module or c.get("classname", "").startswith(module + ".") for c in cases):
            raise ValueError(f"proof not collected: {path}")
        if hashes.get(path) != digest(safe_path(root, path)):
            raise ValueError(f"stale test content: {path}")
    # Different requirement/dependency reports may be separate jobs, but must
    # describe one compatibility row and the same final inputs/commit/profile.
    return json.dumps({**inputs, **artifacts, "seed_commit": env["seed_commit"], "contracts": contracts,
        "execution_profiles": profiles, "credential_profile": credential}, sort_keys=True)


def check_traceability(root: Path, profile: str, *, manifest_path: Path | None = None) -> list[str]:
    if profile not in PROFILES:
        raise ValueError("unknown profile")
    errors = (KeyError, TypeError, ValueError, OSError, EOFError, ET.ParseError, RecursionError)
    try:
        data = read_document(manifest_path or root / "docs/traceability.json")
    except errors as exc:
        return [f"invalid traceability document ({exc})"]
    problems = []
    try:
        inputs = release_inputs(root)
    except errors as exc:
        inputs = None
        problems.append(f"invalid final release inputs ({exc})")

    def rows_for(key):
        rows = data.get(key, [])
        if not isinstance(rows, list):
            problems.append(f"invalid {key} rows")
            return []
        valid = [r for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str)]
        if len(valid) != len(rows):
            problems.append(f"invalid {key} row identity")
        return valid

    rows = rows_for("requirements")
    ids = [row["id"] for row in rows]
    if len(set(ids)) != len(ids):
        problems.append("duplicate requirement IDs")
    if set(ids) != set(REQUIREMENTS):
        problems.append("requirement set differs from frozen plan")
    included = PROFILES[:PROFILES.index(profile) + 1]
    identities = {}
    artifact_cache = {}
    for row in rows:
        if row["id"] not in REQUIREMENTS:
            continue
        required_profile, paths = REQUIREMENTS[row["id"]]
        if required_profile not in included:
            continue
        prefix = row["id"]
        if row.get("status") != "VERIFIED":
            problems.append(f"{prefix}: not VERIFIED")
        if row.get("profile") != required_profile:
            problems.append(f"{prefix}: profile differs from frozen plan")
        if row.get("tests") != list(paths):
            problems.append(f"{prefix}: named proof paths differ")
        for path in paths:
            if not safe_path(root, path).is_file():
                problems.append(f"{prefix}: missing proof {path}")
        try:
            if inputs is None:
                raise ValueError("final pinned inputs are unavailable")
            identity = _consumer_proof(root, row["evidence"], paths, inputs=inputs, profile=required_profile, artifact_cache=artifact_cache)
            if row.get("status") == "VERIFIED" and row.get("profile") == required_profile and row.get("tests") == list(paths):
                identities[prefix] = identity
        except errors as exc:
            problems.append(f"{prefix}: invalid evidence ({exc})")
    if len(set(identities.values())) > 1:
        problems.append("requirement reports describe different compatibility inputs")
    dependency_rows = rows_for("runtime_dependencies")
    dependency_ids = [row["id"] for row in dependency_rows]
    expected_dependencies = {dep for deps in DEPENDENCIES.values() for dep in deps}
    if len(dependency_ids) != len(set(dependency_ids)) or set(dependency_ids) != expected_dependencies:
        problems.append("Runtime dependency set differs from frozen plan")
    for owner in included:
        for dep in DEPENDENCIES[owner]:
            row = next((r for r in dependency_rows if r["id"] == dep), {})
            if row.get("status") != "VERIFIED" or not row.get("evidence"):
                problems.append(f"{dep}: not VERIFIED with consumer evidence")
                continue
            try:
                if inputs is None:
                    raise ValueError("final pinned inputs are unavailable")
                proof = read_document(_verified_file(root, row["evidence"]))
                if proof.get("schema") != "seed-runtime-dependency-proof/v1" or proof.get("dependency") != dep or proof.get("status") != "VERIFIED":
                    raise ValueError("dependency consumer proof identity/status mismatch")
                for field in ("runtime_wheel_sha256", "contract_sha256"):
                    if proof.get(field) != inputs[field]:
                        raise ValueError(f"dependency {field} differs from final pinned inputs")
                required = DEPENDENCY_REQUIREMENTS[dep]
                if proof.get("requirements") != list(required):
                    raise ValueError("dependency named requirements differ")
                if any(name not in identities for name in required):
                    raise ValueError("dependency requirements lack verified consumer evidence")
                paths = tuple(dict.fromkeys(p for name in required for p in REQUIREMENTS[name][1]))
                identity = _consumer_proof(root, proof["consumer_evidence"], paths, inputs=inputs, profile=owner, artifact_cache=artifact_cache)
                if any(identities[name] != identity for name in required):
                    raise ValueError("dependency and requirement reports describe different compatibility inputs")
            except errors as exc:
                problems.append(f"{dep}: invalid consumer evidence ({exc})")
    return sorted(set(problems))
