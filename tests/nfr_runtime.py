"""semantic_observation/v2: root/child normalization of real public records.

Only generated Task/Action/Invocation/Projection/Fact IDs and their derivative
request/manifest identities are renamed. Absolute times, absolute Fact sequence,
observation/meta revisions, authority-use fingerprints and the unused Fact
boundary are excluded after validation. Frozen content, scope, source hashes,
ordered states/reasons, actual request/history and all output hashes remain.
"""

from copy import deepcopy
import json

from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex


async def semantic_observation(client, task_id):
    execution = await client.get_task_execution(task_id)
    trace = await client.get_task_trace(task_id)
    assert trace["resource_type"] == "task-trace/v1" and trace["schema_version"] == 1
    assert trace["status"] == execution["status"] == "SUCCEEDED"
    assert len(trace["actions"]) == 2 and all(a['status']=='SUCCEEDED' for a in trace['actions'])
    assert len(execution["projections"]) == 1
    assert len(execution["invocations"]) == 3
    assert [i["kind"] for i in execution["invocations"]] == ["MODEL", "CAPABILITY", "MODEL"]
    root, child = trace['actions']
    assert root['action_id']==execution['root_action_id']
    assert child['action_id']==execution['invocations'][1]['action_id'] and child['action_id']!=root['action_id']
    assert child['intent']=='capability_tool' and child['causal_parent_action_id']==root['action_id']
    assert child['actor_id']==root['actor_id'] and child['composition_id']==root['composition_id']
    assert child['consumed_budget']['steps']==1 and child['consumed_budget']['effects']==0
    assert execution['invocations'][0]['action_id']==execution['invocations'][2]['action_id']==root['action_id']
    assert all(i["status"] == "SUCCEEDED" and i["error"] is None for i in execution["invocations"])
    assert execution["consumed_budget"] == {"turns": 2, "model_calls": 2, "steps": 3, "effects": 2, "cost_microunits": 0}
    assert trace["actions"][0]["budget"] == execution["budget"]
    assert trace["actions"][0]["consumed_budget"] == execution["consumed_budget"]
    view = json.loads(await client.get_artifact_content(execution["acceptance_view_artifact_id"]))
    assert view["meta_revision"] == execution["accepted_meta_revision"]
    assert view["context_sources"]["fact_boundary_seq"] < execution["accepted_fact_seq"] <= trace["fact_boundary_seq"]
    assert view["context_sources"]["facts_available"] is False and view["context_sources"]["facts"] == []
    assert len(view["authority_fingerprint"]) == 64
    semantic_view = deepcopy(view)
    for key in ("meta_revision", "authority_fingerprint"):
        del semantic_view[key]
    del semantic_view["context_sources"]["fact_boundary_seq"]
    stored = execution["projections"][0]
    manifest = stored["manifest"]
    manifest_bytes = canonical_json(manifest)
    manifest_id = "artifact://sha256/" + sha256_hex(manifest_bytes)
    assert await client.get_artifact_content(manifest_id) == manifest_bytes
    required_manifest = {k: v for k, v in manifest.items() if not k.startswith("x_")}
    assert manifest["meta_revision"] == execution["accepted_meta_revision"]
    assert manifest["x_task_id"] == task_id
    semantic_projection = {k: v for k, v in required_manifest.items() if k not in ("projection_id", "meta_revision")}
    projection_hash = sha256_hex(canonical_json(required_manifest))
    rendered = await client.get_artifact_content(stored["rendered_artifact_id"])
    assert len(rendered) == manifest["total_tokens"] <= manifest["budget_tokens"]
    role = {task_id: "$task", trace["root_action_id"]: "$root-action", manifest_id: "$projection-manifest/0",
        manifest["projection_id"]: "$projection/0", execution["acceptance_view_artifact_id"]: "$acceptance-view",
        child['action_id']:'$tool-action/0'}
    for index, invocation in enumerate(execution["invocations"]):
        role[invocation["invocation_id"]] = f"$invocation/{index}"
    events = trace["events"]
    assert len({e["fact_id"] for e in events}) == len(events)
    assert [e["seq"] for e in events] == sorted({e["seq"] for e in events})
    assert all(e["seq"] <= trace["fact_boundary_seq"] and e["schema_version"] == 1 for e in events)
    for index, event in enumerate(events):
        role[event["fact_id"]] = f"$fact/{index}"
    expected_names = ["task_accepted", "task_started", "action_started", "artifact_registered"]
    quartet = ['invocation_created','invocation_attempted','invocation_attempted','invocation_finished']
    expected_names += quartet + ['action_started'] + quartet + ['action_finished'] + quartet
    expected_names += ["task_succeeded", "action_finished"]
    assert [e["event_type"] for e in events] == expected_names
    assert (events[1]["old_status"], events[1]["new_status"]) == ("ACCEPTED", "RUNNING")
    assert (events[2]["old_status"], events[2]["new_status"]) == ("CREATED", "RUNNING")
    assert events[8]['entity_id']==events[13]['entity_id']==child['action_id']
    assert (events[8]['old_status'],events[8]['new_status'],events[8]['reason_code'])==('CREATED','RUNNING','TOOL_DISPATCHED')
    assert (events[13]['old_status'],events[13]['new_status'],events[13]['reason_code'])==('RUNNING','SUCCEEDED','TOOL_COMMITTED')
    for index, start in enumerate((4,9,14)):
        group = events[start:start+4]
        assert all(e["entity_id"] == execution["invocations"][index]["invocation_id"] for e in group)
        assert [(e["old_status"], e["new_status"]) for e in group] == [(None, None), ("CREATED", "DISPATCHED"), ("DISPATCHED", "RUNNING"), ("RUNNING", "SUCCEEDED")]
    assert [(e["old_status"], e["new_status"]) for e in events[-2:]] == [("RUNNING", "SUCCEEDED")] * 2
    semantic_events = [{k: role.get(e[k], e[k]) for k in ("entity_type", "entity_id", "event_type", "schema_version", "action_id", "old_status", "new_status", "reason_code")} for e in events]
    semantic_edges = sorted((e["edge_type"], role.get(e["from_id"], e["from_id"]), role.get(e["to_id"], e["to_id"]), role[e["source_fact_id"]]) for e in trace["edges"])
    assert len(semantic_edges) == 13
    assert len([e for e in trace['edges'] if e['edge_type']=='authorized_by' and e['from_id']==child['action_id']])==2
    assert any(e['edge_type']=='caused_by' and e['from_id']==child['action_id'] and e['to_id']==root['action_id'] for e in trace['edges'])
    assert any(e['edge_type']=='used' and e['from_id']==child['action_id'] and e['to_id']==execution['invocations'][1]['input_artifact_id'] for e in trace['edges'])
    requests, outputs = [], []
    for invocation in execution["invocations"]:
        request = json.loads(await client.get_artifact_content(invocation["input_artifact_id"]))
        if invocation["kind"] == "MODEL":
            assert request["projection_id"] == manifest["projection_id"]
            assert request["projection_identity_hash"] == projection_hash
            assert request["rendered_artifact_id"] == stored["rendered_artifact_id"]
            request = {**request, "projection_id": "$projection/0", "projection_identity_hash": sha256_hex(canonical_json(semantic_projection))}
        requests.append(request)
        content = await client.get_artifact_content(invocation["output_artifact_id"])
        assert invocation["output_artifact_id"] == "artifact://sha256/" + sha256_hex(content)
        outputs.append({k: invocation[k] for k in ("kind", "target", "attempt", "status", "output_artifact_id", "error", "usage")})
    terminal = await client.get_artifact_content(execution["result_artifact_id"])
    return {"view": semantic_view, "projection": semantic_projection, "rendered_artifact_id": stored["rendered_artifact_id"],
        "actions": [{k: role.get(a[k],a[k]) if k=='causal_parent_action_id' else a[k] for k in ("actor_id", "intent", "composition_id", "grant_id", "causal_parent_action_id", "status", "budget", "consumed_budget", "error")} for a in trace["actions"]],
        "events": semantic_events, "edges": semantic_edges, "requests": requests, "outputs": outputs,
        "terminal_artifact_id": execution["result_artifact_id"], "terminal_hex": terminal.hex()}
