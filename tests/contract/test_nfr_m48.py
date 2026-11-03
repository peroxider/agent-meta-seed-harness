"""NFR-M48: 100 real own-key Tasks, exact inputs and normalized state traces."""

import asyncio
import json
from pathlib import Path

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, TextPart, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

from nfr_runtime import semantic_observation
from seed_actor import create_actor
from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import admin, running_daemon


def test_nfr_m48_hundred_tasks_preserve_frozen_inputs_content_and_ordered_states(tmp_path):
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/nfr_m48.json").read_bytes())
    assert fixture["id"] == "NFR-M48" and fixture["repetitions"] == 100
    assert fixture['normalization']=='tests/nfr_runtime.py:semantic_observation/v2'
    bundle, publisher = seed_bundle()
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        install_seed(data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(data_dir))
        actor = create_actor(data_dir, permissions=["task.submit", "model.invoke", "capability.invoke"], max_uses=500)
        path = tmp_path / "deterministic-input.json"
        path.write_bytes(canonical_json(fixture["input"]))
        reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
        expected = encode_terminal_result(TerminalResult((TextPart("echo complete"),
            JsonPart({"results": [{"value": fixture["input"]["value"]}]}), TextPart("done"))))
        async def scenario():
            client = await connect(data_dir, authority=actor)
            try:
                first, tasks = None, set()
                for _ in range(fixture["repetitions"]):
                    task = await client.submit_task(realm_id="realm://main", actor_id=actor.actor_id,
                        input_artifact_id=reference, budget=fixture["budget"])
                    assert task.task_id not in tasks
                    tasks.add(task.task_id)
                    result, terminal = await client.wait_task(task.task_id, timeout_s=15)
                    assert terminal and result["status"] == "SUCCEEDED", result
                    observed = await semantic_observation(client, task.task_id)
                    assert observed["terminal_artifact_id"] == "artifact://sha256/" + sha256_hex(expected)
                    assert observed["terminal_hex"] == expected.hex()
                    if first is None:
                        first = observed
                        cli_trace = admin(data_dir, "task", "trace", task.task_id)
                        assert cli_trace["events"] == (await client.get_task_trace(task.task_id))["events"]
                    assert observed == first
                assert len(tasks) == 100
            finally:
                await client.aclose()
        asyncio.run(scenario())
