"""Installed-wheel CLI/SDK control plane; bound Host gates remain OPEN.

The published console entry point is run under this exact isolated interpreter.
No Runtime source, key storage, database, CAS or private Python API is inspected.
"""

import asyncio
import json
import os
import subprocess
import sys
import time

from agent_meta_runtime.sdk import connect


CONSOLE = "import importlib.metadata as m; import sys; e=next(e for e in m.distribution('agent-meta-runtime').entry_points if e.group=='console_scripts' and e.name=='agent-meta'); sys.exit(e.load()())"


def cli(data_dir, *arguments):
    fixture = ["--insecure-dev-credential-file"] if os.name != "nt" else []
    return [sys.executable, "-I", "-u", "-c", CONSOLE, "--data-dir", str(data_dir),
            "--output", "json", *fixture, *arguments]


def run(data_dir, *arguments):
    return subprocess.run(cli(data_dir, *arguments), capture_output=True, text=True,
                          cwd=data_dir.parent, timeout=15)


def started(process, output, errors):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"daemon exited {process.returncode}: {errors.read_text()}")
        for line in output.read_text().splitlines():
            try:
                envelope = json.loads(line)
            except ValueError:
                continue
            if envelope.get("ok") and envelope.get("result", {}).get("state") == "RUNNING":
                return envelope["result"]
        time.sleep(.025)
    raise AssertionError("daemon startup deadline expired")


async def inspect(data_dir):
    client = await connect(data_dir)
    try:
        info = await client.get_info()
        return client.server_instance_id, info
    finally:
        await client.aclose()


def test_independent_consumer_initializes_connects_and_stops_real_daemon(tmp_path):
    data_dir = tmp_path / "data"
    result = run(data_dir, "init")
    assert result.returncode == 0
    assert json.loads(result.stdout)["result"]["core_ready"]
    output, errors = tmp_path / "stdout.jsonl", tmp_path / "stderr.txt"
    with output.open("w", encoding="utf-8") as stdout, errors.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(cli(data_dir, "start"), stdout=stdout, stderr=stderr, cwd=tmp_path,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            status = started(process, output, errors)
            identity, info = asyncio.run(inspect(data_dir))
            assert identity == status["instance_id"]
            assert info.live and info.core_ready and not info.serving_ready
            assert status["serving_reasons"] == ["NO_SERVING_COMPOSITION"]
            stopped = run(data_dir, "stop")
            assert stopped.returncode == 0
            assert json.loads(stopped.stdout)["result"]["instance_id"] == identity
            assert process.wait(timeout=10) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    assert run(data_dir, "info").returncode != 0


def test_consumer_observes_exclusive_owner_and_new_identity_after_crash(tmp_path):
    data_dir = tmp_path / "data"
    assert run(data_dir, "init").returncode == 0
    identities = []
    for attempt in range(2):
        output, errors = tmp_path / f"stdout-{attempt}.jsonl", tmp_path / f"stderr-{attempt}.txt"
        with output.open("w", encoding="utf-8") as stdout, errors.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(cli(data_dir, "start"), stdout=stdout, stderr=stderr, cwd=tmp_path,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                status = started(process, output, errors)
                identities.append(status["instance_id"])
                duplicate = run(data_dir, "start")
                assert duplicate.returncode == 12
                assert json.loads(duplicate.stdout)["error"]["code"] == "ALREADY_RUNNING"
                assert run(data_dir, "init").returncode == 12
                if attempt == 0:
                    process.kill()
                    process.wait(timeout=10)
                else:
                    assert run(data_dir, "stop").returncode == 0
                    assert process.wait(timeout=10) == 0
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
    assert len(set(identities)) == 2
