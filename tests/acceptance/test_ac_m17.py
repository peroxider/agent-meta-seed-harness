"""AC-M17: real selected InMemory + own-key Seed fake Model/echo/why."""

import asyncio
import json
import os
from pathlib import Path

from agent_meta_runtime.sdk import AgentMetaClient, LocalTransport
from agent_meta_runtime.sdk.transport import LocalConnection
from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, TextPart, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

from seed_actor import create_actor
from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import admin, daemon_process
from agent_meta_seed_harness.evidence import safe_path


def test_ac_m17_inmemory_context_model_echo_execution_facts_why_completion(tmp_path):
    bundle, publisher = seed_bundle()
    with daemon_process(tmp_path, publishers=[publisher], execution_backend="in_memory") as owner:
        install_seed(owner.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(owner.data_dir))
        actor = create_actor(owner.data_dir, permissions=["task.submit", "model.invoke", "capability.invoke"])
        path = tmp_path / "input.json"
        path.write_bytes(canonical_json({"provider": "fake", "scenario": "echo", "value": "AC-M17 actual activity"}))
        reference = admin(owner.data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
        async def scenario():
            connection = LocalConnection(owner.data_dir / "run/agent-meta.sock")
            await connection.connect()
            transport = LocalTransport(connection)
            client = AgentMetaClient(transport, authority=actor)
            try:
                view = await client.get_view(include_backend=True)
                features = view["backend_profile"]["features"]
                assert features["activity"] == "SUPPORTED" and features["persistent_idempotency"] == "EMULATED"
                assert all(features[key] == "UNSUPPORTED" for key in ("isolated_realm", "network_isolation", "credential_isolation", "hard_memory_quota"))
                task = await client.submit_task(realm_id="realm://main", actor_id=actor.actor_id, input_artifact_id=reference)
                terminal, done = await client.wait_task(task.task_id, timeout_s=15)
                assert done and terminal["status"] == "SUCCEEDED", terminal
                end = asyncio.get_running_loop().time() + 10
                while True:
                    execution = await client.get_task_execution(task.task_id)
                    if all(i.get("execution_binding", {}).get("ack_state") == "ACKNOWLEDGED" for i in execution["invocations"]):
                        break
                    assert asyncio.get_running_loop().time() < end, execution
                    await asyncio.sleep(.02)
                assert [i["kind"] for i in execution["invocations"]] == ["MODEL", "CAPABILITY", "MODEL"]
                assert all(i["status"] == "SUCCEEDED" for i in execution["invocations"])
                accepted = json.loads(await client.get_artifact_content(execution["acceptance_view_artifact_id"]))
                assert accepted["backend_profile_hash"] == view["backend_profile"]["profile_hash"]
                trace = await client.get_task_trace(task.task_id)
                events = [e["event_type"] for e in trace["events"]]
                for event in ("execution_submitted", "execution_bound", "execution_status_observed", "terminal_acknowledged"):
                    assert events.count(event) == 3
                assert events.count("invocation_created") == events.count("invocation_finished") == 3
                root_action, child = trace['actions']
                assert root_action['action_id']==execution['root_action_id'] and root_action['status']=='SUCCEEDED'
                assert execution['invocations'][0]['action_id']==execution['invocations'][2]['action_id']==root_action['action_id']
                assert child['action_id']==execution['invocations'][1]['action_id'] and child['action_id']!=root_action['action_id']
                assert child['intent']=='capability_tool' and child['status']=='SUCCEEDED'
                assert child['causal_parent_action_id']==root_action['action_id']
                assert child['consumed_budget']['steps']==1 and child['consumed_budget']['effects']==0
                assert [e['action_id'] for e in trace['events'] if e['event_type']=='execution_submitted']==[i['action_id'] for i in execution['invocations']]
                edges = trace["edges"]
                assert any(e['edge_type']=='caused_by' and e['from_id']==child['action_id'] and e['to_id']==root_action['action_id'] for e in edges)
                assert len([e for e in edges if e['edge_type']=='authorized_by' and e['from_id']==child['action_id']])==2
                graph = await client.why(task.task_id, max_depth=6)
                for invocation in execution["invocations"]:
                    binding = invocation["execution_binding"]
                    assert binding["backend_id"] == "backend://inmemory" and binding["request_id"] == invocation["invocation_id"]
                    assert binding["payload_hash"] == invocation["input_artifact_id"].rsplit("/", 1)[1]
                    assert len(binding["handle_hash"]) == len(binding["result_hash"]) == 64
                    assert binding["terminal_status"] == "SUCCEEDED"
                    assert not {"opaque_handle", "authority_token", "session_id", "private_key"} & binding.keys()
                    assert await client.get_artifact_content(binding["certificate_artifact_id"])
                    assert any(e["edge_type"] == "executed_as" and e["from_id"] == invocation["invocation_id"] and e["to_id"] == binding["instance_id"] for e in edges)
                    assert invocation["invocation_id"] in canonical_json(graph).decode()
                assert len(execution["projections"]) == 1
                for projection in execution["projections"]:
                    assert projection["action_id"] == execution["root_action_id"]
                    assert await client.get_artifact_content(projection["rendered_artifact_id"])
                expected = encode_terminal_result(TerminalResult((TextPart("echo complete"),
                    JsonPart({"results": [{"value": "AC-M17 actual activity"}]}), TextPart("done"))))
                assert terminal["result_artifact_id"] == "artifact://sha256/" + sha256_hex(expected)
                assert await client.get_artifact_content(terminal["result_artifact_id"]) == expected
                assert execution["consumed_budget"] == {"turns": 2, "model_calls": 2, "steps": 3, "effects": 2, "cost_microunits": 0}
                assert admin(owner.data_dir, "task", "execution", task.task_id)["invocations"] == execution["invocations"]
                validation = await client.validate_harness_package(bundle.manifest_artifact_id)
                assert validation["valid"]
                versions = validation["resolved_contract_versions"]
                assert tuple(map(int, versions["public_api"].split(".")[:2])) == transport.negotiated_version
                root = Path(__file__).resolve().parents[2]
                directory = safe_path(root, os.environ.get("SEED_CONSUMER_REPORT_DIR", "reports/bootstrap"))
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "runtime-observation.json").write_bytes(canonical_json({
                    "schema": "seed-runtime-observation/v1", "run_id": os.environ.get("SEED_CONSUMER_RUN_ID", "standalone"),
                    "package_artifact_id": bundle.package_artifact_id, "package_manifest_artifact_id": bundle.manifest_artifact_id,
                    "publisher_key_sha256": publisher, "credential_profile": owner.credential_profile,
                    "contracts": {"public_api": ".".join(map(str, transport.negotiated_version)),
                        "harness": versions["harness_contract"], "capability": versions["capability_contract"], "artifact_format": "AMPAK1"},
                    "backend_profile": view["backend_profile"], "task_id": task.task_id,
                    "terminal_artifact_id": terminal["result_artifact_id"]}))
            finally:
                await client.aclose()
        asyncio.run(scenario())
