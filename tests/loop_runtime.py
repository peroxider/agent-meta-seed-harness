"""Real public-wheel process and independent scripted package for Loop proofs."""

import asyncio
from pathlib import Path

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json

from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import admin, running_daemon


def scripted_bundle(**options):
    fixtures = Path(__file__).parent / "fixtures"
    return seed_bundle(overrides={"agent_meta_seed_harness/providers/fake.py": (fixtures / "loop_provider.py").read_bytes(),
        "agent_meta_seed_harness/capabilities/echo.py": (fixtures / "loop_echo.py").read_bytes()}, **options)


@pytest.fixture(scope="module")
def loop_runtime(tmp_path_factory):
    root = tmp_path_factory.mktemp("real-loop-host")
    bundle, publisher = scripted_bundle()
    with running_daemon(root, publishers=[publisher]) as data_dir:
        install_seed(data_dir, root, bundle)
        asyncio.run(wait_ready(data_dir))
        yield data_dir, root


def run_workload(runtime, scenario, *, budget=None):
    data_dir, root = runtime
    path = root / "workload.json"
    path.write_bytes(canonical_json({"provider": "fake", "scenario": scenario, "value": "fixture"}))
    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
    options = ["--budget", canonical_json(budget).decode()] if budget is not None else []
    task = admin(data_dir, "task", "submit", "--input-artifact", reference, *options)
    async def observed():
        client = await connect(data_dir)
        try:
            result, terminal = await client.wait_task(task["task_id"], timeout_s=10)
            assert terminal, result
            graph = await client.why(task["task_id"], max_depth=5)
            assert not graph["truncated"]
            execution = await client.get_task_execution(task["task_id"])
            assert execution["status"] == result["status"]
            assert sorted(item["invocation_id"] for item in execution["invocations"]) == sorted(node for node in graph["nodes"] if node.startswith("invocation://"))
            return result, [node for node in graph["nodes"] if node.startswith("invocation://")], reference
        finally:
            await client.aclose()
    return asyncio.run(observed())
