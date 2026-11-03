"""The optional evidence command must reject skips and substituted inputs."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "native_context_verification", ROOT / "scripts/verify_native_context.py"
)
verification = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verification)


def xml_cases(extra="", *, second="False"):
    stem = (
        "test_real_native_root_context_is_independently_counted_or_refused_before_model"
    )
    return (
        f'<testsuites><testsuite><testcase name="{stem}[True]"/>'
        f'<testcase name="{stem}[{second}]">{extra}</testcase></testsuite></testsuites>'
    )


@pytest.mark.parametrize(
    "change", ["skip", "failure", "error", "duplicate", "empty", "collection"]
)
def test_optional_job_cannot_report_a_skip_missing_case_or_collection_error_as_pass(
    tmp_path, change
):
    content = xml_cases()
    if change in ("skip", "failure", "error"):
        content = xml_cases(f'<{"skipped" if change == "skip" else change}/>')
    elif change == "duplicate":
        content = xml_cases(second="True")
    elif change == "empty":
        content = "<testsuites/>"
    else:
        content = content.replace(
            "</testsuites>",
            '<testsuite><error message="collection"/></testsuite></testsuites>',
        )
    path = tmp_path / "junit.xml"
    path.write_text(content)
    with pytest.raises(ValueError, match="both actual cases"):
        verification.verify_cases(path)


def test_both_executed_cases_are_required(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text(xml_cases())
    assert verification.verify_cases(path) == 2


@pytest.mark.parametrize("change", ["editable", "changed", "extra"])
def test_installed_bytes_not_version_claims_establish_wheel_consumption(
    tmp_path, monkeypatch, change
):
    module = "fixture_package"
    site = tmp_path / "site-packages"
    package = site / module
    package.mkdir(parents=True)
    (package / "__init__.py").write_bytes(b"verified = True\n")
    wheel = tmp_path / "fixture.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(module + "/__init__.py", b"verified = True\n")
    distribution = SimpleNamespace(
        version="0.1",
        locate_file=lambda name: site / name,
        read_text=lambda name: json.dumps(
            {"dir_info": {"editable": change == "editable"}}
        ),
    )
    monkeypatch.setattr(
        verification.metadata, "distribution", lambda name: distribution
    )
    monkeypatch.setattr(verification.sys, "prefix", str(tmp_path))
    if change == "changed":
        (package / "__init__.py").write_bytes(b"verified = False\n")
    elif change == "extra":
        (package / "untracked.py").write_bytes(b"unverified = True\n")
    with pytest.raises(ValueError):
        verification.installed_wheel(wheel, module)


def test_existing_receipt_is_preserved_before_any_new_work(tmp_path):
    output = tmp_path / "reports/previous"
    output.mkdir(parents=True)
    (output / "run.json").write_text('{"status":"FAILED"}')
    with pytest.raises(FileExistsError):
        verification.verify(
            tmp_path,
            runtime_wheel=None,
            seed_wheel=None,
            tokenizer_json=None,
            label="previous",
        )
    assert json.loads((output / "run.json").read_text()) == {"status": "FAILED"}
