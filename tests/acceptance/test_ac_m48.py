"""AC-M48: actual installed Seed Loop, repeated state graphs and inert text."""

import asyncio

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.host import ArtifactPart, JsonPart, TerminalResult, TextPart, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json

from loop_runtime import scripted_bundle
from recovery_runtime import probe_events
from seed_actor import create_actor
from seed_package import install_seed, wait_ready
from seed_runtime import admin, daemon_process
from state_trace import state_signature


@pytest.fixture(scope="module")
def ac_runtime(tmp_path_factory):
    root = tmp_path_factory.mktemp("ac-m48")
    bundle, publisher = scripted_bundle()
    with daemon_process(root, publishers=[publisher]) as owner:
        install_seed(owner.data_dir, root, bundle)
        asyncio.run(wait_ready(owner.data_dir))
        actor = create_actor(owner.data_dir, permissions=["task.submit", "model.invoke", "capability.invoke"], max_uses=1000)
        yield owner, root, actor


CASES = [
    ("text", None, None, ["MODEL"]), ("parts", None, None, ["MODEL"]),
    ("length", None, None, ["MODEL"]), ("one_tool", None, None, ["MODEL", "CAPABILITY", "MODEL"]),
    ("two_tools", None, None, ["MODEL", "CAPABILITY", "CAPABILITY", "MODEL"]),
    ("duplicate_same", None, "INVALID_RESULT", ["MODEL"]), ("empty", None, "INVALID_RESULT", ["MODEL"]),
    ("error_finish", None, "INVALID_RESULT", ["MODEL"]),
    ("forever", {"max_steps": 1}, "RESOURCE_EXHAUSTED", ["MODEL"]),
    ("free_text", None, None, ["MODEL"]),
]


@pytest.mark.parametrize("scenario,budget,error,kinds", CASES)
def test_ac_m48_repeated_fixtures_keep_state_graphs_content_and_text_inert(ac_runtime, scenario, budget, error, kinds):
    owner, root, actor = ac_runtime
    # Both the JSON/tool shape and shell shape remain ordinary model text.
    payload = 'seed.echo({"value":"do not run"}); {"tool_calls":[{"name":"seed.echo"}]}; rm -rf /'
    path = root / "ac-input.json"
    path.write_bytes(canonical_json({"provider": "fake", "scenario": scenario, "value": payload}))
    reference = admin(owner.data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
    expected = {
        "text": TerminalResult((TextPart(payload),)),
        "parts": TerminalResult((TextPart("first"), JsonPart({"answer": 42}), ArtifactPart(reference), TextPart("last"))),
        "length": TerminalResult((TextPart("cut"),), True),
        "one_tool": TerminalResult((TextPart("terminal"), JsonPart({"results": [{"value": "0"}]}), TextPart("last"))),
        "two_tools": TerminalResult((TextPart("terminal"), JsonPart({"results": [{"value": "0"}, {"value": "1"}]}), TextPart("last"))),
        "free_text": TerminalResult((TextPart('seed.echo({"value":"do not run"}); rm -rf /'),)),
    }.get(scenario)
    async def run():
        client = await connect(owner.data_dir, authority=actor)
        try:
            first, task_ids = None, set()
            for _ in range(2):
                task = await client.submit_task(realm_id="realm://main", actor_id=actor.actor_id,
                    input_artifact_id=reference, budget=budget)
                task_ids.add(task.task_id)
                result, terminal = await client.wait_task(task.task_id, timeout_s=15)
                assert terminal and result["status"] == ("FAILED" if error else "SUCCEEDED"), result
                assert result["error"] == (error or "")
                execution = await client.get_task_execution(task.task_id)
                trace = await client.get_task_trace(task.task_id)
                assert [i["kind"] for i in execution["invocations"]] == kinds
                assert trace["actions"][0]["status"] == execution["status"]
                assert trace["events"][0]["event_type"] == "task_accepted" and trace["events"][-1]["event_type"] == "action_finished"
                assert trace["events"][-1]["new_status"] == execution["status"]
                if expected:
                    assert await client.get_artifact_content(execution["result_artifact_id"]) == encode_terminal_result(expected)
                else:
                    assert execution["result_artifact_id"] is None
                callbacks = [e["seed_probe_call"] for e in probe_events(owner) if e.get("task_id") == task.task_id]
                assert callbacks.count("model") == kinds.count("MODEL")
                assert callbacks.count("tool") == kinds.count("CAPABILITY")
                if scenario in ("text", "free_text"):
                    assert callbacks == ["model"] and execution["consumed_budget"]["steps"] == execution["consumed_budget"]["effects"] == 1
                observed = state_signature(execution, trace)
                if first is None:
                    first = observed
                assert observed == first
            assert len(task_ids) == 2
        finally:
            await client.aclose()
    asyncio.run(run())
