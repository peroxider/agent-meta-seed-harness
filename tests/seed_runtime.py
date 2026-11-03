"""Public CLI process harness shared by independent consumer tests."""

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time


CONSOLE = "import importlib.metadata as m; import sys; e=next(e for e in m.distribution('agent-meta-runtime').entry_points if e.group=='console_scripts' and e.name=='agent-meta'); sys.exit(e.load()())"


def command(data_dir, *arguments):
    options = ["--insecure-dev-credential-file"] if os.name != "nt" else []
    return [sys.executable, "-I", "-u", "-c", CONSOLE, "--data-dir", str(data_dir), "--output", "json", *options, *arguments]


def invoke(data_dir, *arguments):
    result = subprocess.run(command(data_dir, *arguments), cwd=data_dir.parent, capture_output=True, text=True, timeout=20)
    return result, json.loads(result.stdout)


def admin(data_dir, *arguments):
    result, value = invoke(data_dir, *arguments)
    assert result.returncode == 0 and value["ok"], (result.stdout, result.stderr)
    return value["result"]


@dataclass(frozen=True)
class DaemonProcess:
    data_dir: Path
    process: subprocess.Popen
    output: Path
    errors: Path
    credential_profile: str


@contextmanager
def daemon_process(root: Path, *, publishers=(), label="daemon", execution_backend=None, controlled_provider_test_ca=None):
    data_dir = root / "data"
    initialized = admin(data_dir, "init")
    credential_profile = initialized["features"]["credential_store"]
    output, errors = root / f"{label}-stdout.jsonl", root / f"{label}-stderr.txt"
    arguments = [item for publisher in publishers for item in ("--trusted-publisher", publisher)]
    if execution_backend is not None:
        arguments.extend(("--execution-backend", execution_backend))
    if controlled_provider_test_ca is not None:
        arguments.extend(('--controlled-provider-test-ca',str(controlled_provider_test_ca)))
    with output.open("w", encoding="utf-8") as stdout, errors.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(command(data_dir, "start", *arguments), cwd=root, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            end = time.monotonic() + 15
            while True:
                assert process.poll() is None, errors.read_text()
                started = []
                for line in output.read_text().splitlines():
                    try:
                        started.append(json.loads(line))
                    except ValueError:
                        continue
                if any(item.get("ok") and item.get("result", {}).get("state") == "RUNNING" for item in started):
                    break
                assert time.monotonic() < end, "daemon startup deadline exceeded"
                time.sleep(.025)
            yield DaemonProcess(data_dir, process, output, errors, credential_profile)
            if process.poll() is None:
                admin(data_dir, "stop")
                assert process.wait(timeout=10) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


@contextmanager
def running_daemon(root: Path, *, publishers=(), execution_backend=None):
    with daemon_process(root, publishers=publishers, execution_backend=execution_backend) as owner:
        yield owner.data_dir
