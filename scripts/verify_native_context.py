"""Offline, installed-wheel native Context acceptance with explicit public data.

Install the project's hash-locked dependencies and both wheels first. This
command installs/downloads nothing and never enables a real model Provider.
"""

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def ordinary_bytes(path, maximum):
    path = Path(path)
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise ValueError("ordinary explicit input required")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("input exceeds byte ceiling")
    return raw


def source_inputs(root):
    result = {}
    for directory in (
        "src",
        "tests",
        "scripts",
        "package",
        ".github",
        "docs/plans",
        "docs/runtime-contract",
    ):
        for path in sorted((root / directory).rglob("*")):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix in (".pyc", ".pyo")
            ):
                continue
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("source input escapes checkout")
            result[path.relative_to(root).as_posix()] = digest(
                ordinary_bytes(path, 16 * 1024 * 1024)
            )
    for name in (
        "pyproject.toml",
        "requirements-ci.in",
        "requirements-ci.lock",
        "docs/ci-inputs.json",
        "docs/release-policy.json",
    ):
        result[name] = digest(ordinary_bytes(root / name, 1024 * 1024))
    return result


def installed_wheel(path, module, *, source=None):
    raw = ordinary_bytes(path, 32 * 1024 * 1024)
    distribution = metadata.distribution(module.replace("_", "-"))
    direct = json.loads(distribution.read_text("direct_url.json") or "{}")
    if direct.get("dir_info", {}).get("editable", False):
        raise ValueError("editable installations cannot prove wheel consumption")
    site = Path(distribution.locate_file(module)).resolve()
    if not site.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("package is outside this interpreter environment")
    entries = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.startswith(module + "/") or name.endswith("/"):
                continue
            if name in entries or ".." in Path(name).parts or "\\" in name:
                raise ValueError("ambiguous wheel package path")
            content = archive.read(name)
            relative = Path(name).relative_to(module)
            if ordinary_bytes(site / relative, 4 * 1024 * 1024) != content:
                raise ValueError("installed package differs from explicit wheel")
            if (
                source is not None
                and ordinary_bytes(source / name, 4 * 1024 * 1024) != content
            ):
                raise ValueError("consumer source differs from installed Seed wheel")
            entries[name] = digest(content)
    actual = {
        module + "/" + path.relative_to(site).as_posix()
        for path in site.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in (".pyc", ".pyo")
    }
    if not entries or set(entries) != actual:
        raise ValueError("installed package file set differs from wheel")
    return {
        "wheel_sha256": digest(raw),
        "version": distribution.version,
        "files": entries,
        "editable": False,
    }


def verify_cases(path):
    tree = ET.parse(path)
    cases = list(tree.iter("testcase"))
    expected = {
        "test_real_native_root_context_is_independently_counted_or_refused_before_model[True]",
        "test_real_native_root_context_is_independently_counted_or_refused_before_model[False]",
    }
    if (
        len(cases) != 2
        or {case.get("name") for case in cases} != expected
        or any(list(tree.iter(tag)) for tag in ("failure", "error", "skipped"))
    ):
        raise ValueError(
            "native acceptance requires both actual cases without skips or failures"
        )
    return len(cases)


def verify(root, *, runtime_wheel, seed_wheel, tokenizer_json, label):
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", label) is None:
        raise ValueError("simple unique run label required")
    output = root / "reports" / label
    if output.exists():
        raise FileExistsError("preserve existing evidence; choose a new label")
    # Explicit inputs and actual installations are checked before making output.
    ci = json.loads(ordinary_bytes(root / "docs/ci-inputs.json", 1024 * 1024))
    packages = {
        "agent_meta_runtime": installed_wheel(runtime_wheel, "agent_meta_runtime"),
        "agent_meta_seed_harness": installed_wheel(
            seed_wheel, "agent_meta_seed_harness", source=root / "src"
        ),
    }
    if packages["agent_meta_runtime"]["wheel_sha256"] != ci["runtime_wheel_sha256"]:
        raise ValueError("Runtime wheel differs from this consumer's explicit CI pin")
    lock = json.loads(
        ordinary_bytes(
            root
            / "src/agent_meta_seed_harness/data/provider-tokenizers/glm-5.3-flash-v1.json",
            65536,
        )
    )
    expected = lock["files"]["tokenizer.json"]
    raw = ordinary_bytes(tokenizer_json, expected["bytes"])
    if len(raw) != expected["bytes"] or digest(raw) != expected["sha256"]:
        raise ValueError("tokenizer data differs from frozen public identity")
    if metadata.version("tokenizers") != lock["engine"]["version"]:
        raise ValueError("pinned optional native engine is unavailable")
    inputs = source_inputs(root)
    output.mkdir(parents=True, exist_ok=False)
    (output / "tokenizer.json").write_bytes(raw)
    (output / "inputs.json").write_text(
        json.dumps(inputs, indent=2) + "\n", encoding="utf-8"
    )
    record = {
        "schema": "seed-native-context-acceptance/v1",
        "status": "RUNNING",
        "packages": packages,
        "python": platform.python_version(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "tokenizer_id": lock["tokenizer_id"],
        "vocabulary_sha256": expected["sha256"],
        "engine_version": metadata.version("tokenizers"),
        "external_provider_requests": 0,
        "gateway_request_counting_verified": False,
        "s04_complete": False,
        "release_complete": False,
    }

    def save():
        (output / "run.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )

    save()
    try:
        environment = dict(
            os.environ,
            PIP_NO_INDEX="1",
            PYTHONPATH="",
            PYTEST_ADDOPTS="",
            SEED_NATIVE_CONTEXT_TOKENIZER_JSON=str(output / "tokenizer.json"),
        )
        with (output / "pytest.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "pytest",
                    "tests/acceptance/native_context_probe.py",
                    "-q",
                    "--tb=short",
                    "--junitxml=" + str(output / "junit.xml"),
                ],
                cwd=root,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=240,
            )
        if result.returncode:
            raise ValueError("native acceptance subprocess failed")
        cases = verify_cases(output / "junit.xml")
        if (
            source_inputs(root) != inputs
            or digest((output / "tokenizer.json").read_bytes()) != expected["sha256"]
        ):
            raise ValueError("verification inputs changed during execution")
        for module, path in (
            ("agent_meta_runtime", runtime_wheel),
            ("agent_meta_seed_harness", seed_wheel),
        ):
            if installed_wheel(path, module) != packages[module]:
                raise ValueError("installed package changed during execution")
        record.update(
            status="PASSED",
            cases=cases,
            junit_sha256=digest((output / "junit.xml").read_bytes()),
            inputs_sha256=digest((output / "inputs.json").read_bytes()),
        )
    except BaseException:
        record["status"] = "FAILED"
        save()
        raise
    save()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-wheel", type=Path, required=True)
    parser.add_argument("--seed-wheel", type=Path, required=True)
    parser.add_argument("--tokenizer-json", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    try:
        result = verify(Path(__file__).resolve().parents[1], **vars(args))
    except FileExistsError:
        print(json.dumps({"status": "REFUSED", "error_code": "OUTPUT_EXISTS"}))
        return 3
    except (
        ValueError,
        OSError,
        metadata.PackageNotFoundError,
        ET.ParseError,
        subprocess.TimeoutExpired,
        zipfile.BadZipFile,
    ):
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_code": "NATIVE_CONTEXT_VERIFICATION_UNAVAILABLE",
                }
            )
        )
        return 2
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "cases",
                    "external_provider_requests",
                    "s04_complete",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
