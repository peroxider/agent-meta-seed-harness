"""SH-BOOT-01: pure public imports, arbitrary-directory/offline build."""

from email.parser import BytesParser
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from packaging.requirements import Requirement

import pytest
from agent_meta_seed_harness.boundary import check_project, check_source

ROOT = Path(__file__).resolve().parents[2]


def test_seed_import_graph_uses_only_public_runtime_contract():
    assert check_project(ROOT) == []


@pytest.mark.parametrize("source", [
    "import agent_meta_runtime.adapters.store",
    "from agent_meta_runtime.application import recovery",
    "from agent_meta_runtime import domain",
    "from agent_meta_runtime.sdk.client import _jcs_to_dict",
    "from agent_meta_runtime.protocols._v1 import public_pb2",
    "import importlib as loader; loader.import_module('agent_meta_runtime.adapters.store')",
    "from importlib import import_module as load; load('agent_meta_runtime.domain')",
    "__import__('agent_meta_runtime.adapters')",
    "import importlib; importlib.import_module(target)",
    "import sys; sys.path.insert(0, '../agent-meta-runtime/src')",
    "import sys as system; system.path = []",
    "import sys; sys.path[:] = []",
])
def test_private_import_and_checkout_escape_are_rejected(source):
    assert check_source(source)


def test_public_sdk_imports_are_accepted():
    assert check_source("from agent_meta_runtime.sdk import AgentMetaClient\nfrom agent_meta_runtime.sdk.packages import PackageMeta") == []


def test_contract_bundle_has_explicit_version_and_verified_hashes():
    directory = ROOT / "docs/runtime-contract"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["harness_contract_version"] == "1.1.0"
    assert len(manifest["runtime_wheel_sha256"]) == 64
    assert manifest["runtime_commit"]
    assert manifest["files"]
    paths = [row["path"] for row in manifest["files"]]
    assert len(paths) == len(set(paths))
    for row in manifest["files"]:
        path = (directory / row["path"]).resolve()
        assert path.is_relative_to(directory.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_ci_lock_has_exact_versions_and_hashes_without_source_paths():
    lines = [line for line in (ROOT / "requirements-ci.lock").read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    assert any(line.startswith("agent-meta-runtime==0.1.0.dev1 ") for line in lines)
    for line in lines:
        assert "==" in line and " --hash=sha256:" in line
        assert len(line.rsplit(":", 1)[1]) == 64
        assert all(char not in line for char in ("/", "\\", "@"))


def test_relocated_checkout_builds_wheel_offline_without_runtime_sources(tmp_path):
    relocated = tmp_path / "arbitrary checkout"
    relocated.mkdir()
    for name in ("src", "scripts", "tests", "docs"):
        shutil.copytree(ROOT / name, relocated / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("pyproject.toml", "README.md", "LICENSE", "requirements-ci.lock", "CHANGELOG.md"):
        shutil.copyfile(ROOT / name, relocated / name)
    environment = dict(os.environ, PIP_NO_INDEX="1", PYTHONPATH="", PYTHONNOUSERSITE="1")
    result = subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--wheel", str(relocated)], cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = list((relocated / "dist").glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        assert any(name.startswith("agent_meta_seed_harness/") for name in archive.namelist())
        assert not any(name.startswith(("tests/", "agent_meta_runtime/")) for name in archive.namelist())
        metadata = BytesParser().parsebytes(archive.read(next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))))
        assert metadata["Name"] == "agent-meta-seed-harness"
        requirements = [Requirement(value) for value in metadata.get_all("Requires-Dist")]
        assert {str(value) for value in requirements if value.marker is None} == {"agent-meta-runtime==0.1.0.dev1", "cryptography>=43"}
        optional = [value for value in requirements if value.marker is not None]
        expected_extras = {
            "scratch": {"ipykernel==7.4.0", "ipython==9.18.0", "jupyter-client==8.10.0"},
            "tokenizer-preparation": {"tokenizers==0.23.3"},
        }
        assert {value.name + str(value.specifier) for value in optional} == set().union(*expected_extras.values())
        for extra, expected in expected_extras.items():
            assert {value.name + str(value.specifier) for value in optional
                if value.marker.evaluate({'extra': extra})} == expected
        assert all(not value.marker.evaluate({'extra': ''}) for value in optional)
        for name in archive.namelist():
            assert str(ROOT).encode() not in archive.read(name)


def test_runtime_consumer_uses_the_exact_locked_wheel_without_editable_sources():
    distribution = importlib.metadata.distribution("agent-meta-runtime")
    assert distribution.version == "0.1.0.dev1"
    direct = json.loads(distribution.read_text("direct_url.json") or "{}")
    assert not direct.get("dir_info", {}).get("editable", False)
    assert distribution.files
    assert not any(str(path).endswith(".pth") for path in distribution.files)
    inputs = json.loads((ROOT / "docs/ci-inputs.json").read_text(encoding="utf-8"))
    wheel_input = next(row for row in inputs["wheels"] if row["name"] == "agent-meta-runtime")
    wheel = ROOT / "wheelhouse" / wheel_input["filename"]
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == wheel_input["sha256"]
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith("agent_meta_runtime/") and not name.endswith("/"):
                assert distribution.locate_file(name).read_bytes() == archive.read(name), name
