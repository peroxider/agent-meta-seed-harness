"""Synthetic reports test the gate itself; never product acceptance evidence."""

import json
import copy
import io
import tarfile
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent_meta_seed_harness.packaging import EXECUTION_SOURCE_PATHS, build_bundle
from agent_meta_seed_harness.release_artifacts import verify_candidate_artifacts
from agent_meta_seed_harness.release import ReleaseNotReady, release_candidate
from agent_meta_seed_harness.evidence import (
    DEPENDENCIES, DEPENDENCY_REQUIREMENTS, PROFILES, REQUIREMENTS, check_traceability, digest, safe_path, release_inputs,
)


def write(root, path, content):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(content)
    return {"path": path, "sha256": digest(file)}


def synthetic_artifacts(root, inputs):
    """Minimal unit shapes; never an installed or product acceptance proof."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("agent_meta_seed_harness-0.1.0.dev1.dist-info/METADATA", "Name: agent-meta-seed-harness\nVersion: 0.1.0.dev1\nRequires-Dist: agent-meta-runtime==0.1.0.dev1\n")
        for path in (root / "src").rglob("*.py"):
            archive.writestr(path.relative_to(root / "src").as_posix(), path.read_bytes())
    wheel = write(root, "reports/synthetic/seed.whl", output.getvalue())
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        files = [p for d in ("src", "tests", "scripts", "package", ".github", "docs/plans") for p in (root / d).rglob("*") if p.is_file()]
        for path in [*files, root / "pyproject.toml", root / "requirements-ci.in", root / "requirements-ci.lock", root / ".gitignore", root / "docs/release-policy.json"]:
            archive.add(path, arcname="agent_meta_seed_harness-0.1.0.dev1/" + path.relative_to(root).as_posix())
    sdist = write(root, "reports/synthetic/seed.tar.gz", output.getvalue())
    components = [{"name": "agent-meta-runtime", "version": "0.1.0.dev1", "hashes": [{"alg": "SHA-256", "content": inputs["runtime_wheel_sha256"]}]},
        {"name": "agent-meta-seed-harness", "version": "0.1.0.dev1", "hashes": [{"alg": "SHA-256", "content": wheel["sha256"]}]}]
    sbom = write(root, "reports/synthetic/sbom.cdx.json", json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.6", "components": components}).encode())
    provenance = write(root, "reports/synthetic/provenance.json", json.dumps({"schema": "seed-development-build/v1", "status": "DEVELOPMENT_NOT_RELEASED",
        "seed_source_sha256": inputs["seed_source_sha256"], "fixture_sha256": inputs["fixture_sha256"], "lock_sha256": inputs["lock_sha256"],
        "contract_bundle_sha256": inputs["contract_sha256"], "ci_inputs_sha256": digest(root / "docs/ci-inputs.json"),
        "artifacts": {Path(r["path"]).name: r["sha256"] for r in (wheel, sdist, sbom)}}).encode())
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    bundle = build_bundle(files={name: (root / "src" / name).read_bytes() for name in EXECUTION_SOURCE_PATHS},
        dependency_lock=(root / "requirements-ci.lock").read_bytes(), publisher_public_key=key.public_key().public_bytes_raw(),
        signer=key, contract_bundle_sha256=inputs["contract_sha256"])
    bundle.write(root / "reports/synthetic/package")
    refs = {"seed_wheel": wheel, "seed_sdist": sdist, "seed_sbom": sbom, "seed_provenance": provenance,
        "package_bundle": {"path": "reports/synthetic/package/bundle.json", "sha256": digest(root / "reports/synthetic/package/bundle.json")}}
    return refs, verify_candidate_artifacts(root, refs, inputs=inputs)


def fixture(root):
    """Construct isolated evidence shapes to exercise validation, not a release."""
    suite = ET.Element("testsuite")
    requirements = []
    for name, (profile, paths) in REQUIREMENTS.items():
        row = {"id": name, "profile": profile, "tests": list(paths), "status": "PLANNED", "evidence": None}
        if profile == "minimal":
            row["status"] = "VERIFIED"
            for path in paths:
                write(root, path, b"def test_synthetic():\n    assert True\n")
                ET.SubElement(suite, "testcase", classname=path.removesuffix(".py").replace("/", "."), name="test_synthetic")
        requirements.append(row)
    junit = write(root, "reports/synthetic/junit.xml", ET.tostring(suite))
    # These minimal archives/documents are unit-test shapes only; real public
    # wheel/package proof is owned by test_release_evidence.py.
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("agent_meta_runtime-0.1.0.dev1.dist-info/METADATA", "Name: agent-meta-runtime\nVersion: 0.1.0.dev1\n")
    runtime_wheel = write(root, "wheelhouse/runtime.whl", output.getvalue())
    proto = write(root, "docs/runtime-contract/proto/public.proto", b"// synthetic contract\n")
    contract = write(root, "docs/runtime-contract/manifest.json", json.dumps({"schema": "seed-runtime-contract-bundle/v1",
        "runtime_wheel_sha256": runtime_wheel["sha256"], "runtime_version": "0.1.0.dev1", "harness_contract_version": "1.1.0",
        "files": [{"path": "proto/public.proto", "sha256": proto["sha256"]}]}).encode())
    write(root, "pyproject.toml", b'[project]\nname="agent-meta-seed-harness"\nversion="0.1.0.dev1"\ndependencies = ["agent-meta-runtime==0.1.0.dev1"]\n')
    write(root, "requirements-ci.in", b"# synthetic preparation inputs\n")
    write(root, ".gitignore", b"reports/\n")
    write(root, "docs/plans/synthetic-scope.md", b"# Synthetic release scope\n")
    write(root, "requirements-ci.lock", f"agent-meta-runtime==0.1.0.dev1 --hash=sha256:{runtime_wheel['sha256']}\n".encode())
    write(root, "tests/fixtures/fixture.json", b'{"synthetic":true}\n')
    write(root, "docs/ci-inputs.json", json.dumps({"schema": "seed-ci-inputs/v1", "runtime_wheel_sha256": runtime_wheel["sha256"],
        "os": "Windows", "python": "3.12.14", "architecture": "AMD64", "wheels": [{"name": "agent-meta-runtime", "filename": "runtime.whl", "version": "0.1.0.dev1", "sha256": runtime_wheel["sha256"]}]}).encode())
    for name in EXECUTION_SOURCE_PATHS:
        write(root, "src/" + name, b"# synthetic unit shape; no executable adapter\n")
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    from agent_meta_runtime.sdk.packages import sha256_hex
    write(root, "docs/release-policy.json", json.dumps({"schema": "seed-release-policy/v1",
        "approved_publishers": [sha256_hex(key.public_key().public_bytes_raw())]}).encode())
    inputs = release_inputs(root)
    artifacts, identities = synthetic_artifacts(root, inputs)
    environment = write(root, "reports/synthetic/environment.json", json.dumps({
        **inputs, **identities, "schema": "seed-consumer-evidence/v1", "status": "VERIFIED", "profile": "minimal",
        "seed_commit": "a" * 40, "junit_sha256": junit["sha256"],
        "execution_profiles": ["in_memory", "trusted_in_process"], "credential_profile": "WINDOWS_DPAPI_CURRENT_USER",
        "contracts": {"public_api": "1.6", "harness": "1.1.0", "capability": "1.0.0", "artifact_format": "AMPAK1"},
        "command": ["python", "-I", "-m", "pytest"],
    }).encode())
    for row in requirements:
        if row["status"] == "VERIFIED":
            row["evidence"] = {"junit": junit, "environment": environment, "runtime_wheel": runtime_wheel, "contract_bundle": contract, "artifacts": artifacts,
                "test_hashes": {path: digest(root / path) for path in row["tests"]}}
    consumer = {**requirements[0]["evidence"], "test_hashes": {path: digest(root / path)
        for row in requirements if row["profile"] == "minimal" for path in row["tests"]}}
    deps = []
    for profile, names in DEPENDENCIES.items():
        for name in names:
            evidence = write(root, f"reports/synthetic/{name}.json", json.dumps({"schema": "seed-runtime-dependency-proof/v1", "dependency": name,
                "status": "VERIFIED", "runtime_wheel_sha256": runtime_wheel["sha256"], "contract_sha256": contract["sha256"],
                "requirements": list(DEPENDENCY_REQUIREMENTS[name]), "consumer_evidence": consumer}).encode())
            deps.append({"id": name, "status": "VERIFIED" if profile == "minimal" else "OPEN", "evidence": evidence if profile == "minimal" else None})
    document = {"requirements": requirements, "runtime_dependencies": deps}
    save(root, document)
    assert check_traceability(root, "minimal") == [], "negative-case fixture must start from a consistent shape"
    return document


def mutate_dependency(root, data, change):
    reference = data["runtime_dependencies"][0]["evidence"]
    document = json.loads((root / reference["path"]).read_bytes())
    change(document)
    data["runtime_dependencies"][0]["evidence"] = write(root, reference["path"], json.dumps(document).encode())
    save(root, data)


def save(root, document):
    write(root, "docs/traceability.json", json.dumps(document).encode())


def test_consistent_synthetic_evidence_is_readable(tmp_path):
    fixture(tmp_path)
    assert check_traceability(tmp_path, "minimal") == []


def test_candidate_references_exact_tested_artifacts_without_rebuilding(tmp_path):
    data = fixture(tmp_path)
    refs = data["requirements"][0]["evidence"]["artifacts"]
    before = {key: digest(tmp_path / ref["path"]) for key, ref in refs.items()}
    candidate = release_candidate(tmp_path, "minimal")
    assert candidate["status"] == "READY_FOR_OPERATOR_REVIEW"
    assert candidate["artifacts"] == refs
    assert candidate["identities"]["seed_wheel_sha256"] == before["seed_wheel"]
    assert before == {key: digest(tmp_path / ref["path"]) for key, ref in refs.items()}
    assert release_candidate(tmp_path, "minimal") == candidate
    data["requirements"][0]["status"] = "IN_PROGRESS"
    save(tmp_path, data)
    with pytest.raises(ReleaseNotReady):
        release_candidate(tmp_path, "minimal")


@pytest.mark.parametrize("mutation", ["duplicate", "unknown", "planned", "missing_test", "stale_test", "bad_hash", "missing_dependency", "unbound_dependency", "zero_tests", "skipped", "failed"])
def test_gate_rejects_incomplete_or_stale_evidence(tmp_path, mutation):
    data = fixture(tmp_path)
    row = data["requirements"][0]
    if mutation == "duplicate":
        data["requirements"].append(row)
    elif mutation == "unknown":
        row["id"] = "SH-INVENTED-01"
    elif mutation == "planned":
        row["status"] = "PLANNED"
    elif mutation == "missing_test":
        (tmp_path / row["tests"][0]).unlink()
    elif mutation == "stale_test":
        (tmp_path / row["tests"][0]).write_bytes(b"# test removed\n")
    elif mutation == "bad_hash":
        row["evidence"]["junit"]["sha256"] = "0" * 64
    elif mutation == "missing_dependency":
        data["runtime_dependencies"][0]["status"] = "OPEN"
    elif mutation == "unbound_dependency":
        proof = data["runtime_dependencies"][0]["evidence"]
        proof.update(write(tmp_path, proof["path"], b'{"status":"VERIFIED"}'))
    else:
        path = tmp_path / row["evidence"]["junit"]["path"]
        tree = ET.parse(path)
        suite = tree.getroot()
        if mutation == "zero_tests":
            suite.clear()
        else:
            ET.SubElement(next(suite.iter("testcase")), "skipped" if mutation == "skipped" else "failure")
        tree.write(path)
        row["evidence"]["junit"]["sha256"] = digest(path)
    save(tmp_path, data)
    assert check_traceability(tmp_path, "minimal")


def test_expanded_profile_requires_minimal_and_new_proofs(tmp_path):
    fixture(tmp_path)
    issues = check_traceability(tmp_path, "provider")
    assert any("SH-PROV-03" in issue for issue in issues)
    assert any("RP-03" in issue for issue in issues)


@pytest.mark.parametrize("mutation", ["runtime_wheel", "contract", "bare", "missing_consumer", "requirements", "different_commit", "uncollected"])
def test_dependency_needs_same_final_inputs_and_actual_named_consumer_report(tmp_path, mutation):
    data = fixture(tmp_path)
    def change(document):
        if mutation in ("runtime_wheel", "contract"):
            document["runtime_wheel_sha256" if mutation == "runtime_wheel" else "contract_sha256"] = "0" * 64
        elif mutation == "bare":
            document.clear()
            document.update({"dependency": "RP-00", "status": "VERIFIED", "runtime_wheel_sha256": "0" * 64, "contract_sha256": "1" * 64})
        elif mutation == "missing_consumer":
            document.pop("consumer_evidence")
        elif mutation == "requirements":
            document["requirements"] = ["SH-BOOT-01"]
        else:
            proof = copy.deepcopy(document["consumer_evidence"])
            env = json.loads((tmp_path / proof["environment"]["path"]).read_bytes())
            if mutation == "different_commit":
                env["seed_commit"] = "b" * 40
            else:
                suite = ET.Element("testsuite")
                ET.SubElement(suite, "testcase", classname="tests.unit.unrelated", name="test_shape")
                proof["junit"] = write(tmp_path, "reports/synthetic/dependency-only.xml", ET.tostring(suite))
                env["junit_sha256"] = proof["junit"]["sha256"]
            proof["environment"] = write(tmp_path, "reports/synthetic/dependency-only.json", json.dumps(env).encode())
            document["consumer_evidence"] = proof
    mutate_dependency(tmp_path, data, change)
    issues = check_traceability(tmp_path, "minimal")
    assert any(issue.startswith("RP-00: invalid consumer evidence") for issue in issues), issues


@pytest.mark.parametrize("field,value", [("schema", "seed-development-evidence/v1"), ("status", "DEVELOPMENT_ONLY"),
    ("seed_commit", "a" * 41), ("fixture_sha256", "b" * 64), ("lock_sha256", "0" * 64), ("runtime_wheel_sha256", "0" * 64),
    ("contract_sha256", "0" * 64), ("runtime_version", "9.9.9"), ("python", "3.13"), ("os", "Linux"),
    ("profile", "invalid"), ("command", ["pytest"]), ("credential_profile", "INSECURE_TEST_ONLY"),
    ("contracts", {}), ("execution_profiles", ["trusted_in_process"]), ("junit_sha256", "0" * 64),
    ("seed_wheel_sha256", "0" * 64), ("seed_sdist_sha256", "0" * 64), ("package_artifact_id", "artifact://sha256/" + "0" * 64),
    ("package_manifest_artifact_id", "artifact://sha256/" + "0" * 64), ("publisher_key_sha256", "0" * 64)])
def test_release_cannot_promote_development_or_unbound_environment(tmp_path, field, value):
    data = fixture(tmp_path)
    row = data["requirements"][0]
    env = json.loads((tmp_path / row["evidence"]["environment"]["path"]).read_bytes())
    env[field] = value
    row["evidence"]["environment"] = write(tmp_path, "reports/synthetic/changed-environment.json", json.dumps(env).encode())
    save(tmp_path, data)
    issues = check_traceability(tmp_path, "minimal")
    assert any(issue.startswith("SH-BOOT-01: invalid evidence") for issue in issues), issues


@pytest.mark.parametrize("content", [b'[]', b'{"requirements":null}', b'{"requirements":[null]}',
    b'{"requirements":[],"requirements":[]}', b'{"requirements":NaN}'])
def test_malformed_traceability_is_a_failed_gate_not_an_uncaught_exception(tmp_path, content):
    fixture(tmp_path)
    write(tmp_path, "docs/traceability.json", content)
    assert check_traceability(tmp_path, "minimal")


@pytest.mark.parametrize("mutation", ["lock", "contract_file", "contract_duplicate", "wheel", "project", "ci_hash"])
def test_pinned_inputs_are_verified_before_accepting_reports(tmp_path, mutation):
    fixture(tmp_path)
    if mutation == "lock":
        write(tmp_path, "requirements-ci.lock", b"agent-meta-runtime==0.1.0.dev1 --hash=sha256:" + b"0" * 64 + b"\n")
    elif mutation == "contract_file":
        write(tmp_path, "docs/runtime-contract/proto/public.proto", b"modified contract")
    elif mutation == "contract_duplicate":
        path = tmp_path / "docs/runtime-contract/manifest.json"
        data = json.loads(path.read_bytes())
        data["files"].append(data["files"][0])
        path.write_text(json.dumps(data))
    elif mutation == "wheel":
        write(tmp_path, "wheelhouse/runtime.whl", b"not a wheel")
    elif mutation == "project":
        write(tmp_path, "pyproject.toml", b'[project]\ndependencies=["agent-meta-runtime>=0.1"]\n')
    else:
        path = tmp_path / "docs/ci-inputs.json"
        data = json.loads(path.read_bytes())
        data["runtime_wheel_sha256"] = "0" * 64
        path.write_text(json.dumps(data))
    assert any(issue.startswith("invalid final release inputs") for issue in check_traceability(tmp_path, "minimal"))


def test_release_publisher_requires_reviewed_policy_instead_of_a_self_declared_key(tmp_path):
    data = fixture(tmp_path)
    policy = tmp_path / "docs/release-policy.json"
    policy.write_text('{"schema":"seed-release-policy/v1","approved_publishers":[]}')
    # Merely updating the top-level policy and source hash cannot authorize a
    # different immutable candidate or preserve a report from its earlier run.
    assert check_traceability(tmp_path, "minimal")


def test_development_collection_parser_preserves_nested_classes_and_parameter_ids():
    import runpy
    script = Path(__file__).resolve().parents[2] / "scripts/record_development_evidence.py"
    parse = runpy.run_path(str(script))["collection_identities"]
    assert parse("tests/contract/test_one.py::Group::test_case[artifact::id]\n1 test collected\n") == {
        ("tests.contract.test_one.Group", "test_case[artifact::id]")}


def test_collector_ignores_inherited_filters_and_preserves_existing_report(tmp_path, monkeypatch):
    import runpy
    script = Path(__file__).resolve().parents[2] / "scripts/record_development_evidence.py"
    require = runpy.run_path(str(script))["require_full_collection"]
    cases = []
    for directory in ("unit", "contract", "acceptance"):
        path = tmp_path / "tests" / directory / ("test_" + directory + ".py")
        path.parent.mkdir(parents=True)
        path.write_text("def test_collected():\n    assert True\n")
        cases.append(ET.Element("testcase", classname=f"tests.{directory}.test_{directory}", name="test_collected"))
    report = tmp_path / "must-preserve.xml"
    report.write_bytes(b"previous report bytes")
    monkeypatch.setenv("PYTEST_ADDOPTS", f"--junitxml={report.as_posix()} -k never_selected_case")
    require(tmp_path, cases)
    assert report.read_bytes() == b"previous report bytes"
    with pytest.raises(ValueError, match="complete current"):
        require(tmp_path, cases[:1])
    assert report.read_bytes() == b"previous report bytes"


@pytest.mark.parametrize("path", ["../secret", "C:/secret", "a\\b", "/outside", "a//b", "", "./x"])
def test_evidence_path_escape_is_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, path)


@pytest.mark.parametrize("profile,required,present,excluded", [
    ("evolution-artifact", ("SH-EVO-03", "SH-EVO-04"), ("SH-GOV-03",), ("SH-EVO-05", "SH-GOV-04")),
    ("evolution-code", ("SH-EVO-03", "SH-EVO-04", "SH-EVO-05", "SH-GOV-04"), ("SH-GOV-03",), ()),
])
def test_evolution_extension_profiles_require_their_missing_named_proofs(profile, required, present, excluded):
    root = Path(__file__).resolve().parents[2]
    issues = check_traceability(root, profile)
    for name in required:
        assert f"{name}: not VERIFIED" in issues
        assert any(issue.startswith(f"{name}: missing proof ") for issue in issues)
    # Proofs that already landed stay unverified until release evidence, but
    # no longer count as missing.
    for name in present:
        assert f"{name}: not VERIFIED" in issues
        assert not any(issue.startswith(f"{name}: missing proof ") for issue in issues)
    for name in excluded:
        assert not any(issue.startswith(name + ":") for issue in issues)
    assert any(issue.startswith("SH-EVO-01:") for issue in issues)
    assert any(issue.startswith("SH-BOOT-01:") for issue in issues)


@pytest.mark.parametrize("profile", ["evolution-artifact", "evolution-code"])
def test_evolution_reports_cannot_authorize_extension_profiles(tmp_path, profile):
    from agent_meta_seed_harness.evidence import _consumer_proof
    data = fixture(tmp_path)
    proof = copy.deepcopy(data["requirements"][0]["evidence"])
    environment = json.loads((tmp_path / proof["environment"]["path"]).read_bytes())
    environment["profile"] = "evolution"
    proof["environment"] = write(tmp_path, proof["environment"]["path"], json.dumps(environment).encode())
    with pytest.raises(ValueError, match="consumer profile does not cover requirement"):
        _consumer_proof(tmp_path, proof, REQUIREMENTS["SH-BOOT-01"][1],
            inputs=release_inputs(tmp_path), profile=profile)


def test_evolution_profile_plan_and_ci_choices_match_the_machine_gate():
    import re
    root = Path(__file__).resolve().parents[2]
    plan = (root / "docs/plans/v0.1/seed-harness/Seed_Harness_Traceability.md").read_text(encoding="utf-8")
    planned = set(re.findall(r"^\| (SH-[A-Z]+-\d+) \|", plan, re.M))
    assert planned == {name for name in REQUIREMENTS if name.startswith("SH-")}
    ledger = json.loads((root / "docs/traceability.json").read_bytes())
    assert {row["id"] for row in ledger["requirements"]} == set(REQUIREMENTS)
    for workflow in ("ci.yml", "release.yml"):
        content = (root / ".github/workflows" / workflow).read_text(encoding="utf-8")
        block = re.search(r"(?ms)^      profile:\n(.*?)(?=^      \w+:|^permissions:)", content).group(1)
        choices = re.search(r"options: \[([^\]]+)\]", block).group(1)
        assert tuple(item.strip() for item in choices.split(",")) == PROFILES
    assert PROFILES[-2:] == ("evolution-artifact", "evolution-code")


def test_plan_changes_invalidate_existing_release_evidence(tmp_path):
    fixture(tmp_path)
    before = release_inputs(tmp_path)["seed_source_sha256"]
    plan = tmp_path / "docs/plans/synthetic-scope.md"
    plan.write_bytes(plan.read_bytes() + b"\nAdditional required acceptance scope.\n")
    assert release_inputs(tmp_path)["seed_source_sha256"] != before
    issues = check_traceability(tmp_path, "minimal")
    assert any("invalid evidence" in issue and "seed_source_sha256" in issue for issue in issues)
