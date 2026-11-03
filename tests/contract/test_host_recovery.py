"""SH-REC-01: confirmed/UNKNOWN model recovery after actual owner process loss."""

import asyncio

import pytest

from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

from recovery_runtime import probe_events, terminal_execution, wait_invocations
from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import admin, daemon_process


PROVIDER = b'''
import asyncio
import json
import uuid
from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import JsonPart, ModelResponse, ProviderUsage
from agent_meta_runtime.sdk.packages import canonical_json

async def invoke_fake(request):
    nonce = uuid.uuid4().hex
    print(canonical_json({"seed_probe_call": request.request_id, "nonce": nonce}).decode(), flush=True)
    if json.loads(rendered_sections(request.projection)["task_input"])["scenario"] == "unknown":
        await asyncio.Event().wait()
    return ModelResponse((JsonPart({"nonce": nonce}),), "STOP", ProviderUsage(None, None, 0))
'''

LOOP = b'''
import asyncio
from agent_meta_runtime.sdk.host import terminal_result
from .context import project

async def run_task(task, host):
    response = await host.invoke_model(await project(task, host))
    # Consumer scheduling window after a durably confirmed result, before Task
    # terminal. No Runtime state/readiness or private fault hook is involved.
    await asyncio.sleep(3)
    return terminal_result(response)
'''


@pytest.mark.parametrize("confirmed", [False, True])
@pytest.mark.parametrize("execution_backend", ["trusted_in_process", "in_memory"])
def test_owner_loss_preserves_confirmed_result_or_stops_unknown_without_redispatch(tmp_path, confirmed, execution_backend):
    bundle, publisher = seed_bundle(overrides={"agent_meta_seed_harness/providers/fake.py": PROVIDER,
        "agent_meta_seed_harness/loop.py": LOOP})
    with daemon_process(tmp_path, publishers=[publisher], label="first", execution_backend=execution_backend) as first:
        install_seed(first.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(first.data_dir))
        path = tmp_path / "input.json"
        path.write_bytes(canonical_json({"provider": "fake", "scenario": "confirmed" if confirmed else "unknown", "value": "fixture"}))
        reference = admin(first.data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
        task_id = admin(first.data_dir, "task", "submit", "--input-artifact", reference)["task_id"]
        before = asyncio.run(wait_invocations(first.data_dir, task_id, statuses=["SUCCEEDED" if confirmed else "RUNNING"]))
        calls = probe_events(first)
        assert len(calls) == 1 and before["status"] == "RUNNING"
        first.process.kill()
        first.process.wait(timeout=10)
    with daemon_process(tmp_path, publishers=[publisher], label="restarted", execution_backend=execution_backend) as restarted:
        asyncio.run(wait_ready(restarted.data_dir))
        result, after = asyncio.run(terminal_execution(restarted.data_dir, task_id))
        assert probe_events(restarted) == []  # independently observed Provider callback count
        assert after["consumed_budget"]["model_calls"] == before["consumed_budget"]["model_calls"] == 1
        assert after["projections"] == before["projections"]
        assert [item["invocation_id"] for item in after["invocations"]] == [item["invocation_id"] for item in before["invocations"]]
        if execution_backend == "in_memory" and confirmed:
            # Only acknowledgement observation can advance after the process
            # loss; the actual handle/audit/result binding stays identical.
            old, new = before["invocations"][0]["execution_binding"], after["invocations"][0]["execution_binding"]
            assert old["ack_state"] in ("PENDING", "ACKNOWLEDGED")
            assert new["ack_state"] in ("PENDING", "ACKNOWLEDGED", "UNAVAILABLE_SESSION_LOST")
            if old["ack_state"] == "ACKNOWLEDGED":
                assert new["ack_state"] == "ACKNOWLEDGED"
            old["ack_state"] = new["ack_state"]
        if confirmed:
            assert after["consumed_budget"] == before["consumed_budget"]
            assert result["status"] == "SUCCEEDED" and after["invocations"] == before["invocations"], result
            expected = encode_terminal_result(TerminalResult((JsonPart({"nonce": calls[0]["nonce"]}),)))
            assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(expected)
        else:
            assert result["status"] == "FAILED_RECOVERY" and result["error"] == "EXTERNAL_EFFECT_UNKNOWN", result
            assert after["invocations"][0]["status"] == "FAILED"
            assert after["invocations"][0]["error"] == "EXTERNAL_EFFECT_UNKNOWN"
            assert after["consumed_budget"]["cost_microunits"] is None
            if execution_backend == "in_memory":
                assert after["invocations"][0]["execution_binding"]["terminal_status"] == "UNKNOWN"
