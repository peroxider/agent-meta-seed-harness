"""Offline developer commands. Product Host commands are gated by RP-00/01."""

import argparse
from pathlib import Path
import tomllib

from .boundary import check_project
from .packaging import EXECUTION_SOURCE_PATHS, TOOLS_EXECUTION_SOURCE_PATHS, build_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agent-meta-seed")
    sub = parser.add_subparsers(dest="command", required=True)
    boundary = sub.add_parser("check-boundary")
    boundary.add_argument("root", type=Path)
    package = sub.add_parser("build-package", aliases=["build-probe"])
    package.add_argument("root", type=Path)
    package.add_argument("--publisher-key", required=True, type=Path, help="operator-provided raw Ed25519 key file; never included in output")
    package.add_argument("--contract-sha256", required=True)
    package.add_argument("--output", required=True, type=Path)
    package.add_argument("--descriptor-revision", type=int, default=1)
    package.add_argument('--profile', choices=('minimal', 'tools'), default='minimal', help='development package source and tool declaration set')
    args = parser.parse_args(argv)
    issues = check_project(args.root)
    if issues:
        for issue in issues:
            print(issue)
        return 1
    if args.command == "check-boundary":
        return 0
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(args.publisher_key.read_bytes())
    # Explicit source allowlist prevents venv, tests, keys or local reports
    # from accidentally becoming executable package payload.
    files = {}
    for relative in TOOLS_EXECUTION_SOURCE_PATHS if args.profile == 'tools' else EXECUTION_SOURCE_PATHS:
        path = args.root / "src" / relative
        if path.is_symlink() or not path.resolve().is_relative_to(args.root.resolve()):
            raise ValueError("source symlinks are not package inputs")
        files[path.relative_to(args.root / "src").as_posix()] = path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
    project = tomllib.loads((args.root / "pyproject.toml").read_text(encoding="utf-8"))
    if project["project"]["version"] != "0.1.0.dev1":
        raise ValueError("update the manifest SemVer mapping for this distribution version")
    bundle = build_bundle(
        files=files, dependency_lock=(args.root / "requirements-ci.lock").read_bytes(),
        publisher_public_key=key.public_key().public_bytes_raw(), signer=key,
        contract_bundle_sha256=args.contract_sha256,
        descriptor_revision=args.descriptor_revision,
        tools=args.profile == 'tools',
    )
    bundle.write(args.output)
    print(bundle.manifest_artifact_id)
    return 0
