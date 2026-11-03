"""Prepare a reviewable release candidate from already tested artifacts."""

from .evidence import PROFILES, REQUIREMENTS, DEPENDENCIES, _verified_file, check_traceability, digest, read_document, release_inputs
from .release_artifacts import verify_candidate_artifacts


class ReleaseNotReady(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__("required consumer evidence is incomplete")


def release_candidate(root, profile):
    """No build, signing, publishing or activation occurs in this function."""
    issues = check_traceability(root, profile)
    if issues:
        raise ReleaseNotReady(issues)
    ledger_path = root / "docs/traceability.json"
    ledger_hash = digest(ledger_path)
    ledger = read_document(ledger_path)
    included = PROFILES[:PROFILES.index(profile) + 1]
    requirements = [row for row in ledger["requirements"] if REQUIREMENTS[row["id"]][0] in included]
    dependency_ids = {name for owner in included for name in DEPENDENCIES[owner]}
    dependencies = [row for row in ledger["runtime_dependencies"] if row["id"] in dependency_ids]
    proof = next(row["evidence"] for row in requirements if row["id"] == "SH-REL-02")
    environment = read_document(_verified_file(root, proof["environment"]))
    inputs = release_inputs(root)
    artifacts = verify_candidate_artifacts(root, proof["artifacts"], inputs=inputs)
    if any(environment.get(field) != value for field, value in {**inputs, **artifacts}.items()) or digest(ledger_path) != ledger_hash:
        raise ReleaseNotReady(["release inputs changed during candidate preparation"])
    return {"schema": "seed-release-candidate/v1", "status": "READY_FOR_OPERATOR_REVIEW", "profile": profile,
        "seed_commit": environment["seed_commit"], "inputs": inputs, "identities": artifacts,
        "contracts": environment["contracts"], "execution_profiles": environment["execution_profiles"],
        "credential_profile": environment["credential_profile"], "artifacts": proof["artifacts"],
        "traceability_sha256": ledger_hash, "requirements": requirements, "runtime_dependencies": dependencies}
