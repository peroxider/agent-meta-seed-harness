"""Online, explicit preparation phase. No discovery of adjacent checkouts.

Accepts a Runtime CI wheel and its expected hash. Resolves only binary wheels,
then writes a platform-specific hash lock. Review lock changes before use.
"""

from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile


def wheel_identity(path):
    with zipfile.ZipFile(path) as wheel:
        names = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError("expected exactly one wheel METADATA")
        metadata = BytesParser().parsebytes(wheel.read(names[0]))
    return metadata["Name"], metadata["Version"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-wheel", type=Path, required=True)
    parser.add_argument("--runtime-sha256", required=True)
    parser.add_argument("--update-lock", action="store_true", help="explicitly permit dependency resolution and replace the platform lock")
    parser.add_argument("--offline", action="store_true", help="resolve only wheels already in this project's explicit wheelhouse")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    wheel = args.runtime_wheel.resolve(strict=True)
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != args.runtime_sha256:
        raise ValueError("Runtime wheel hash differs from explicit input")
    if wheel_identity(wheel) != ("agent-meta-runtime", "0.1.0.dev1"):
        raise ValueError("Runtime wheel identity differs from pinned project dependency")
    offline = ["--no-index", "--find-links", str(root / "wheelhouse")] if args.offline else []
    if not args.update_lock:
        subprocess.run([sys.executable, "-m", "pip", "download", *offline, "--only-binary=:all:", "--require-hashes", "--find-links", str(wheel.parent), "--dest", str(root / "wheelhouse"), "-r", str(root / "requirements-ci.lock")], check=True)
        return 0
    # Resolve in a fresh directory so stale wheels cannot enter the lock/SBOM.
    with tempfile.TemporaryDirectory(prefix="seed-wheelhouse-") as temp:
        target = Path(temp)
        subprocess.run([sys.executable, "-m", "pip", "download", *offline, "--only-binary=:all:", "--dest", str(target), str(wheel), "-r", str(root / "requirements-ci.in")], check=True)
        entries = []
        seen = set()
        artifacts = []
        for path in sorted(target.glob("*.whl")):
            name, version = wheel_identity(path)
            normalized = name.lower().replace("_", "-").replace(".", "-")
            if normalized in seen:
                raise ValueError("duplicate distribution in resolved wheelhouse")
            seen.add(normalized)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append((normalized, f"{normalized}=={version} --hash=sha256:{digest}"))
            artifacts.append({"filename": path.name, "name": name, "version": version, "sha256": digest})
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir(exist_ok=True)
        for path in target.glob("*.whl"):
            shutil.copyfile(path, wheelhouse / path.name)
        header = f"# CPython {sys.version_info.major}.{sys.version_info.minor} / {platform.system()} {platform.machine()}\n# Prepared from explicit Runtime CI wheel; no editable/source dependency.\n"
        (root / "requirements-ci.lock").write_text(header + "\n".join(line for _, line in sorted(entries)) + "\n", encoding="utf-8", newline="\n")
        (root / "docs/ci-inputs.json").write_text(json.dumps({"schema": "seed-ci-inputs/v1", "python": platform.python_version(), "os": platform.system(), "architecture": platform.machine(), "runtime_wheel_sha256": args.runtime_sha256, "wheels": artifacts}, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
