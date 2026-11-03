"""Verify candidate distribution/AMPAK coherence without executing a package.

This certifies bytes and input binding, never a release verdict or publisher
approval. The separate reviewed consumer evidence and release gate own those.
"""

from email.parser import BytesParser
import hashlib
from pathlib import Path
import re
import tarfile
import tomllib
import zipfile
import zlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from agent_meta_runtime.sdk.packages import AmpakError, decode_package, manifest_signature_preimage, validate_manifest

from .evidence import _verified_file, digest, read_document, safe_path
from .packaging import EXECUTION_SOURCE_PATHS


ARTIFACT_FIELDS = ("seed_wheel", "seed_sdist", "seed_sbom", "seed_provenance", "package_bundle")


def verify_candidate_artifacts(root: Path, references: dict, *, inputs: dict) -> dict:
    if not isinstance(references, dict) or set(references) != set(ARTIFACT_FIELDS):
        raise ValueError("complete candidate distribution and signed AMPAK references required")
    paths = {key: _verified_file(root, references[key]) for key in ARTIFACT_FIELDS}
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    wheel, sdist = paths["seed_wheel"], paths["seed_sdist"]
    if wheel.stat().st_size > 64 * 1024 * 1024 or sdist.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("candidate distribution exceeds byte ceiling")
    try:
        with zipfile.ZipFile(wheel) as archive:
            members = archive.namelist()
            if len(members) > 20000 or sum(i.file_size for i in archive.infolist()) > 128 * 1024 * 1024:
                raise ValueError("candidate wheel expansion exceeds ceiling")
            metadata = [n for n in members if n.endswith(".dist-info/METADATA")]
            if len(members) != len(set(members)) or len(metadata) != 1 or archive.getinfo(metadata[0]).file_size > 1024 * 1024:
                raise ValueError("candidate Seed wheel has ambiguous metadata/members")
            value = BytesParser().parsebytes(archive.read(metadata[0]))
            if value["Name"] != "agent-meta-seed-harness" or value["Version"] != version:
                raise ValueError("candidate Seed distribution identity mismatch")
            if "agent-meta-runtime==" + inputs["runtime_version"] not in value.get_all("Requires-Dist", []):
                raise ValueError("candidate Seed wheel lacks exact Runtime dependency")
            actual = {n for n in members if n.startswith("agent_meta_seed_harness/") and not n.endswith("/")}
            expected = {p.relative_to(root / "src").as_posix(): p for p in (root / "src/agent_meta_seed_harness").rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")}
            if actual != set(expected) or any(archive.getinfo(n).file_size != expected[n].stat().st_size or archive.read(n) != expected[n].read_bytes() for n in actual):
                raise ValueError("candidate Seed wheel differs from final source")
            if any(n.startswith(("tests/", "agent_meta_runtime/")) or n.endswith((".key", ".pem")) for n in members):
                raise ValueError("forbidden candidate wheel content")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error):
        raise ValueError("candidate Seed wheel is not an archive") from None
    try:
        with tarfile.open(sdist, "r:gz") as archive:
            members, total = [], 0
            for member in archive:
                total += member.size
                members.append(member)
                if len(members) > 20000 or total > 128 * 1024 * 1024:
                    raise ValueError("candidate sdist expansion exceeds ceiling")
            names = [m.name for m in members]
            if len(names) != len(set(names)) or any(m.issym() or m.islnk() for m in members):
                raise ValueError("candidate sdist contains duplicate/link entries")
            prefix = "agent_meta_seed_harness-" + version + "/"
            for member in members:
                if not member.name.startswith(prefix) or any(part in ("", ".", "..") for part in member.name.removeprefix(prefix).split("/")):
                    raise ValueError("candidate sdist path is invalid")
            expected = [p for d in ("src", "tests", "scripts", "package", ".github") for p in (root / d).rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")]
            expected += [root / n for n in ("pyproject.toml", "requirements-ci.in", "requirements-ci.lock", ".gitignore", "docs/release-policy.json")]
            for source in expected:
                member = archive.getmember(prefix + source.relative_to(root).as_posix())
                if not member.isfile() or member.size != source.stat().st_size or archive.extractfile(member).read() != source.read_bytes():
                    raise ValueError("candidate sdist differs from final source/lock")
    except (tarfile.TarError, KeyError, EOFError, OSError):
        raise ValueError("candidate sdist is incomplete or invalid") from None
    provenance = read_document(paths["seed_provenance"])
    if provenance.get("schema") != "seed-development-build/v1" or provenance.get("status") != "DEVELOPMENT_NOT_RELEASED":
        raise ValueError("unknown candidate build provenance")
    for field in ("seed_source_sha256", "fixture_sha256", "lock_sha256"):
        if provenance.get(field) != inputs[field]:
            raise ValueError("candidate provenance differs from final " + field)
    if provenance.get("contract_bundle_sha256") != inputs["contract_sha256"] or provenance.get("ci_inputs_sha256") != digest(root / "docs/ci-inputs.json"):
        raise ValueError("candidate provenance differs from pinned Runtime inputs")
    expected_artifacts = {p.name: digest(p) for key, p in paths.items() if key in ("seed_wheel", "seed_sdist", "seed_sbom")}
    if provenance.get("artifacts") != expected_artifacts:
        raise ValueError("candidate provenance artifact hashes differ")
    sbom = read_document(paths["seed_sbom"])
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.6" or not isinstance(sbom.get("components"), list):
        raise ValueError("candidate SBOM is missing")
    ci = read_document(root / "docs/ci-inputs.json")
    components = sbom["components"]
    if len(components) != len(ci["wheels"]) + 1 or not all(isinstance(row, dict) for row in components):
        raise ValueError("candidate SBOM component set differs from lock")
    expected_components = {(r["name"], r["version"], r["sha256"]) for r in ci["wheels"]}
    expected_components.add(("agent-meta-seed-harness", version, digest(wheel)))
    actual_components = set()
    for component in components:
        hashes = component.get("hashes")
        if not isinstance(hashes, list) or len(hashes) != 1 or not isinstance(hashes[0], dict) or hashes[0].get("alg") != "SHA-256":
            raise ValueError("candidate SBOM component hash is missing")
        actual_components.add((component["name"], component["version"], hashes[0]["content"]))
    if actual_components != expected_components:
        raise ValueError("candidate SBOM hashes differ from final artifacts")

    marker_path = paths["package_bundle"]
    marker = read_document(marker_path)
    ids = marker.get("artifact_ids")
    if marker.get("schema") != "seed-package-bundle/v1" or not isinstance(ids, list) or not ids or len(ids) > 4096 or not all(isinstance(v, str) and re.fullmatch(r"artifact://sha256/[0-9a-f]{64}", v) for v in ids) or ids != sorted(set(ids)):
        raise ValueError("candidate AMPAK Artifact closure is invalid")
    blobs = {}
    total = 0
    for reference in ids:
        relative = (marker_path.parent / "artifacts" / reference.rsplit("/", 1)[1]).relative_to(root).as_posix()
        path = safe_path(root, relative)
        total += path.stat().st_size
        if total > 64 * 1024 * 1024 or digest(path) != reference.rsplit("/", 1)[1]:
            raise ValueError("candidate AMPAK Artifact closure hash/size mismatch")
        blobs[reference] = path.read_bytes()
    try:
        manifest_id, package_id = marker["manifest_artifact_id"], marker["package_artifact_id"]
        if not isinstance(manifest_id, str) or not isinstance(package_id, str) or manifest_id not in blobs or package_id not in blobs:
            raise ValueError("candidate AMPAK identity is absent from closure")
        manifest = read_document(safe_path(root, (marker_path.parent / "artifacts" / manifest_id.rsplit("/", 1)[1]).relative_to(root).as_posix()))
        if manifest_id not in blobs or package_id not in blobs or validate_manifest(manifest) or manifest["package_artifact_id"] != package_id:
            raise ValueError("candidate Harness manifest is invalid")
        copies = {"package.ampak": package_id, "manifest.json": manifest_id,
            "composition.json": manifest["composition_template_artifact_id"], "loop-policy.json": manifest["loop_policy_artifact_id"],
            "grant-requests.json": manifest["grant_requests_artifact_id"], "provenance.json": manifest["build_provenance_artifact_id"],
            "publisher.ed25519.pub": manifest["publisher_identity_artifact_id"], "signature.ed25519": manifest["signature_artifact_id"]}
        copies.update({f"capabilities/{index:03d}.json": ref for index, ref in enumerate(manifest["capability_descriptor_artifact_ids"])})
        for name, ref in copies.items():
            path = safe_path(root, (marker_path.parent / name).relative_to(root).as_posix())
            if ref not in blobs or path.stat().st_size != len(blobs[ref]) or path.read_bytes() != blobs[ref]:
                raise ValueError("candidate AMPAK review copy differs from signed Artifact")
        public_key = blobs[manifest["publisher_identity_artifact_id"]]
        Ed25519PublicKey.from_public_bytes(public_key).verify(blobs[manifest["signature_artifact_id"]], manifest_signature_preimage(manifest))
        package, files = decode_package(blobs[package_id])
        if package.package.name != "agent-meta-seed-harness" or package.package.version != version.replace(".dev", "-dev.") or manifest["package_version"] != package.package.version:
            raise ValueError("candidate AMPAK and distribution versions differ")
        if package.package.build_provenance_artifact_id != manifest["build_provenance_artifact_id"]:
            raise ValueError("candidate AMPAK provenance identity differs")
        if set(files) != set(EXECUTION_SOURCE_PATHS) or any(files[n] != (root / "src" / n).read_bytes() for n in files):
            raise ValueError("candidate AMPAK differs from final execution source")
        if blobs[package.package.dependency_lock_artifact_id] != (root / "requirements-ci.lock").read_bytes():
            raise ValueError("candidate AMPAK dependency lock differs")
        lock_copy = safe_path(root, (marker_path.parent / "dependency-lock.txt").relative_to(root).as_posix())
        if lock_copy.read_bytes() != blobs[package.package.dependency_lock_artifact_id]:
            raise ValueError("candidate AMPAK review lock differs")
        package_provenance = read_document(safe_path(root, (marker_path.parent / "artifacts" / manifest["build_provenance_artifact_id"].rsplit("/", 1)[1]).relative_to(root).as_posix()))
        if package_provenance.get("source_files") != {n: hashlib.sha256(raw).hexdigest() for n, raw in sorted(files.items())} or package_provenance.get("contract_bundle_sha256") != inputs["contract_sha256"]:
            raise ValueError("candidate AMPAK provenance input hashes differ")
        for field in ("composition_template_artifact_id", "grant_requests_artifact_id", "loop_policy_artifact_id", "build_provenance_artifact_id"):
            if manifest[field] not in blobs:
                raise ValueError("candidate Harness closure is incomplete")
        if any(ref not in blobs for ref in manifest["capability_descriptor_artifact_ids"]):
            raise ValueError("candidate Capability closure is incomplete")
    except (KeyError, TypeError, AmpakError, InvalidSignature) as exc:
        raise ValueError("candidate AMPAK content/signature/closure is invalid") from exc
    return {**{key + "_sha256": digest(paths[key]) for key in ARTIFACT_FIELDS},
        "package_artifact_id": package_id, "package_manifest_artifact_id": manifest_id,
        "publisher_key_sha256": hashlib.sha256(public_key).hexdigest()}
