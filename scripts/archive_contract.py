"""Archive explicit, versioned contract inputs; builds never read their source."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--runtime-commit", required=True)
    parser.add_argument("--runtime-wheel-sha256", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", args.runtime_commit):
        raise ValueError("Runtime commit must be a full lowercase Git object ID")
    if not re.fullmatch(r"[0-9a-f]{64}", args.runtime_wheel_sha256):
        raise ValueError("Runtime wheel hash must be lowercase SHA-256")
    args.source = args.source.resolve(strict=True)
    root = Path(__file__).resolve().parents[1]
    destination = root / "docs/runtime-contract"
    destination.mkdir(parents=True, exist_ok=True)
    inputs = ["docs/Agent_Meta_Runtime_Requirements_Design_v0.1.md", "docs/spec/v0.1-scope-and-traceability.md", "docs/spec/v0.1-implementation-handoff.md", "docs/adr/031-public-harness-consumer-contract.md", "docs/adr/032-public-host-spi.md", "docs/adr/033-local-command-authority-and-credential-storage.md"]
    inputs.append("docs/adr/034-signed-activation-plan-and-delegation.md")
    inputs.append("docs/adr/035-local-daemon-lifecycle.md")
    inputs.append("docs/adr/036-task-free-factories-and-async-reconciliation.md")
    inputs.append("docs/adr/037-bound-trusted-host-and-durable-invocation-journal.md")
    inputs.append("docs/adr/038-harness-source-audit-and-serving-recovery.md")
    inputs.append("docs/adr/039-frozen-context-policy-and-host-recomputation.md")
    inputs.append("docs/adr/040-public-task-execution-inspection.md")
    inputs.append("docs/adr/041-installation-reference-and-grant-generation-guards.md")
    inputs.append("docs/adr/042-public-ordinary-artifact-content.md")
    inputs.append("docs/adr/043-strict-task-submission-scalars.md")
    inputs.append("docs/adr/044-public-ordinary-principals-and-delegation.md")
    inputs.append("docs/adr/045-cooperative-host-call-scheduling.md")
    inputs.append("docs/adr/046-public-task-state-trace.md")
    inputs.append("docs/adr/047-root-certified-service-execution-tokens.md")
    inputs.append("docs/adr/048-inmemory-session-outcome-and-retention-contract.md")
    inputs.append("docs/adr/049-bootstrap-public-service-certificate.md")
    inputs.append("docs/adr/050-inmemory-host-activity-and-durable-ack.md")
    inputs.extend([
        "docs/adr/051-controlled-provider-edge-and-worker-ownership.md",
        "docs/adr/052-durable-provider-invocation-accounting.md",
        "docs/adr/053-provider-dispatch-and-durable-terminal-edge.md",
        "docs/adr/054-public-provider-plan-and-normalization-spi.md",
        "docs/adr/055-provider-profile-approval-and-frozen-pricing.md",
        "docs/adr/056-provider-credential-provisioning-and-reviewable-cli.md",
        "docs/adr/057-frozen-provider-admission-and-controlled-daemon-assembly.md",
        "docs/adr/058-explicit-native-provider-test-launch.md",
        "docs/adr/059-provider-terminal-observation-and-public-accounting.md",
        "docs/adr/060-task-scoped-meta-resource-host.md",
        "docs/adr/061-public-managed-state-commands.md",
        "docs/adr/062-tool-child-actions-and-execution-bindings.md",
        "docs/adr/063-independent-trusted-scratch-worker-foundation.md",
        "docs/adr/064-bounded-static-scratch-observation.md",
        "docs/adr/065-source-only-scratch-candidate-construction.md",
        "docs/adr/066-transactional-scratch-session-cell-journal.md",
        "docs/adr/067-authorized-owned-scratch-execution.md",
        "docs/adr/068-public-async-scratch-create-execute-release.md",
        "docs/adr/069-public-bounded-scratch-observation.md",
        "docs/adr/070-public-source-only-scratch-export.md",
        "docs/adr/071-owned-scratch-composition-retirement.md",
        "docs/adr/072-portable-windows-owned-worker-lifecycle.md",
        "docs/adr/073-installed-seed-scratch-consumer.md",
        "docs/adr/074-provider-protocol-field-positions.md",
        "docs/adr/075-verified-staging-native-restore.md",
        "docs/adr/076-root-owned-native-context-tokenization.md",
    ])
    inputs.extend(path.relative_to(args.source).as_posix() for path in sorted((args.source / "proto").rglob("*.proto")))
    files = []
    for relative in inputs:
        source = args.source / relative
        if source.is_symlink() or not source.resolve(strict=True).is_relative_to(args.source):
            raise ValueError("contract input must stay inside the explicit source directory")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append({"path": relative, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    manifest = {"schema": "seed-runtime-contract-bundle/v1", "harness_contract_version": "1.1.0", "runtime_version": "0.1.0.dev1", "runtime_commit": args.runtime_commit, "runtime_wheel_sha256": args.runtime_wheel_sha256, "source_state": "development-worktree", "files": files}
    (destination / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(hashlib.sha256((destination / "manifest.json").read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
