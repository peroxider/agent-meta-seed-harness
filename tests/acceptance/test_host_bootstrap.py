"""Independent installed-wheel + real daemon + signed Seed AMPAK.

Only public SDK/CLI and this consumer's own package/resources are accessed.
Runtime key storage, database, CAS and source checkout are never read.
"""

import asyncio
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, TextPart, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_seed_harness.packaging import EXECUTION_SOURCE_PATHS, build_bundle
from seed_package import seed_bundle


CONSOLE = "import importlib.metadata as m; import sys; e=next(e for e in m.distribution('agent-meta-runtime').entry_points if e.group=='console_scripts' and e.name=='agent-meta'); sys.exit(e.load()())"


def command(data_dir, *arguments):
    options = ["--insecure-dev-credential-file"] if os.name != "nt" else []
    return [sys.executable, "-I", "-u", "-c", CONSOLE, "--data-dir", str(data_dir), "--output", "json", *options, *arguments]


def admin(data_dir, *arguments):
    result = subprocess.run(command(data_dir, *arguments), cwd=data_dir.parent, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, (result.stdout, result.stderr)
    value = json.loads(result.stdout)
    assert value["ok"], value
    return value["result"]


async def wait_ready(data_dir, *, serving, revision):
    client = await connect(data_dir)
    try:
        end = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < end:
            info = await client.get_info()
            if info.serving_ready == serving and info.serving_revision == revision:
                return
            await asyncio.sleep(.02)
        raise AssertionError(f"serving cutover did not complete: {info}")
    finally:
        await client.aclose()


def test_real_seed_package_executes_normalized_loop_and_survives_restart(tmp_path):
    project = Path(__file__).resolve().parents[2]
    bundle, publisher = seed_bundle()
    manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
    data_dir = tmp_path / "data"
    admin(data_dir, "init")
    harness_id = None
    interrupted_task = None
    for incarnation in range(2):
        output, errors = tmp_path / f"stdout-{incarnation}.jsonl", tmp_path / f"stderr-{incarnation}.txt"
        with output.open("w", encoding="utf-8") as stdout, errors.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(command(data_dir, "start", "--trusted-publisher", publisher), stdout=stdout, stderr=stderr,
                cwd=tmp_path, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                end = time.monotonic() + 15
                while True:
                    assert process.poll() is None, errors.read_text()
                    if any('"RUNNING"' in line for line in output.read_text().splitlines()):
                        break
                    assert time.monotonic() < end
                    time.sleep(.025)
                if incarnation == 0:
                    artifact_dir = tmp_path / "consumer-artifacts"
                    artifact_dir.mkdir()
                    for reference, raw in bundle.artifacts.items():
                        path = artifact_dir / reference.rsplit("/", 1)[1]
                        path.write_bytes(raw)
                        stored = admin(data_dir, "artifact", "put", str(path), "--kind", "code", "--media-type", "application/octet-stream")
                        assert stored["artifact_id"] == reference
                    report = admin(data_dir, "harness", "validate", bundle.manifest_artifact_id)
                    assert report["valid"], report
                    installed = admin(data_dir, "harness", "install", "--name", manifest["package_name"], "--version", manifest["package_version"],
                        bundle.manifest_artifact_id, bundle.package_artifact_id)
                    harness_id = installed["harness_id"]
                    requests = json.loads(bundle.artifacts[manifest["grant_requests_artifact_id"]])["requests"]
                    grants = [argument for request in requests for argument in ("--grant", canonical_json(request).decode())]
                    admin(data_dir, "harness", "activate", harness_id, manifest["composition_template_artifact_id"], *grants)
                asyncio.run(wait_ready(data_dir, serving=True, revision=1))
                if incarnation == 1:
                    async def recovered():
                        client = await connect(data_dir)
                        try:
                            result, done = await client.wait_task(interrupted_task, timeout_s=5)
                            assert done and result["status"] == "FAILED_RECOVERY" and result["error"] == "EXTERNAL_EFFECT_UNKNOWN", result
                            graph = await client.why(interrupted_task)
                            assert len([node for node in graph["nodes"] if node.startswith("invocation://")]) == 1
                        finally:
                            await client.aclose()
                    asyncio.run(recovered())
                if incarnation == 0:
                    for scenario, code, budget in (("invalid_arguments", "INVALID_RESULT", None),
                        ("unknown_tool", "AUTHORITY_DENIED", None), ("duplicate_calls", "INVALID_RESULT", None),
                        ("echo", "RESOURCE_EXHAUSTED", {"max_steps": 1})):
                        path = tmp_path / f"negative-{scenario}.json"
                        path.write_bytes(canonical_json({"provider": "fake", "scenario": scenario}))
                        reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
                        options = ["--budget", canonical_json(budget).decode()] if budget else []
                        rejected_task = admin(data_dir, "task", "submit", "--input-artifact", reference, *options)["task_id"]
                        async def rejected():
                            client = await connect(data_dir)
                            try:
                                value, terminal = await client.wait_task(rejected_task, timeout_s=5)
                                assert terminal and value["status"] == "FAILED" and value["error"] == code, value
                                graph = await client.why(rejected_task)
                                assert len([node for node in graph["nodes"] if node.startswith("invocation://")]) == 1
                            finally:
                                await client.aclose()
                        asyncio.run(rejected())
                scenarios = [(scenario, "你好", "你好") for scenario in (
                    ("terminal", "echo", "two_echo", "free_text", "length") if incarnation == 0 else ("echo",))]
                if incarnation == 0:
                    scenarios.append(("terminal", "Bearer conformance-secret", "[REDACTED]"))
                for scenario, raw_value, projected_value in scenarios:
                    path = tmp_path / (scenario + ".json")
                    path.write_bytes(canonical_json({"provider": "fake", "scenario": scenario, "value": raw_value}))
                    input_ref = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input", "--media-type", "application/json")["artifact_id"]
                    task = admin(data_dir, "task", "submit", "--input-artifact", input_ref)
                    async def wait_result():
                        client = await connect(data_dir)
                        try:
                            value, terminal = await client.wait_task(task["task_id"], timeout_s=5)
                            assert terminal and value["status"] == "SUCCEEDED", value
                            assert (await client.verify_artifact(value["result_artifact_id"]))[0]
                            graph = await client.why(task["task_id"])
                            count = {"echo": 3, "two_echo": 4}.get(scenario, 1)
                            assert not graph["truncated"]
                            assert len([node for node in graph["nodes"] if node.startswith("invocation://")]) == count
                            return value, await client.get_artifact_content(value["result_artifact_id"])
                        finally:
                            await client.aclose()
                    terminal, result_content = asyncio.run(wait_result())
                    if scenario in ("echo", "two_echo"):
                        values = [{"value": "你好"}] if scenario == "echo" else [{"value": "你好0"}, {"value": "你好1"}]
                        expected = TerminalResult((TextPart("echo complete"), JsonPart({"results": values}), TextPart("done")))
                    elif scenario == "free_text":
                        expected = TerminalResult((TextPart('seed.echo({"value":"must not execute"})'),))
                    else:
                        expected = TerminalResult((TextPart(projected_value), JsonPart({"provider": "fake"}), TextPart("done")), scenario == "length")
                    assert terminal["result_artifact_id"] == "artifact://sha256/" + sha256_hex(encode_terminal_result(expected))
                    assert result_content == encode_terminal_result(expected)
                if incarnation == 1:
                    admin(data_dir, "harness", "deactivate", harness_id)
                    asyncio.run(wait_ready(data_dir, serving=False, revision=0))
                    admin(data_dir, "harness", "uninstall", harness_id)
                    assert admin(data_dir, "harness", "inspect", harness_id)["status"] == "UNINSTALLED"
                if incarnation == 0:
                    path = tmp_path / "wait.json"
                    path.write_bytes(canonical_json({"provider": "fake", "scenario": "wait"}))
                    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
                    interrupted_task = admin(data_dir, "task", "submit", "--input-artifact", reference)["task_id"]
                    async def dispatched():
                        client = await connect(data_dir)
                        try:
                            end = asyncio.get_running_loop().time() + 5
                            while asyncio.get_running_loop().time() < end:
                                graph = await client.why(interrupted_task)
                                if any(node.startswith("invocation://") for node in graph["nodes"]):
                                    assert (await client.get_task(interrupted_task))["status"] == "RUNNING"
                                    return
                                await asyncio.sleep(.01)
                            raise AssertionError("Provider invocation was never durably dispatched")
                        finally:
                            await client.aclose()
                    asyncio.run(dispatched())
                    process.kill()
                    process.wait(timeout=10)
                else:
                    admin(data_dir, "stop")
                    assert process.wait(timeout=10) == 0
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
