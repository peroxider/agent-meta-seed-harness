"""Normalize only identity/time observations, retaining actual state semantics.

Generated Task/Action/Invocation/Projection/Fact IDs and their manifest identities
are replaced by ordered roles. Absolute times/sequences/revisions are excluded.
Frozen content/source refs, targets, output hashes, statuses/reasons, budgets,
usage, actor/grant identities and causal-edge source Fact positions remain.
"""

from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex


def state_signature(execution, trace):
    assert trace["task_id"] == execution["task_id"] and trace["status"] == execution["status"]
    role = {trace["task_id"]: "$task"}
    for index, action in enumerate(trace["actions"]):
        role[action["action_id"]] = "$action/" + str(index)
    for index, invocation in enumerate(execution["invocations"]):
        role[invocation["invocation_id"]] = "$invocation/" + str(index)
    for index, projection in enumerate(execution["projections"]):
        role[projection["projection_id"]] = "$projection/" + str(index)
        role["artifact://sha256/" + sha256_hex(canonical_json(projection["manifest"]))] = "$projection-manifest/" + str(index)
    assert [e["seq"] for e in trace["events"]] == sorted({e["seq"] for e in trace["events"]})
    for index, event in enumerate(trace["events"]):
        role[event["fact_id"]] = "$fact/" + str(index)
    return {"task": {k: execution[k] for k in ("status", "error", "input_artifact_id", "serving_composition_id", "serving_revision",
            "capability_surface_artifact_id", "state_snapshot", "budget", "consumed_budget", "result_artifact_id")},
        "actions": [{k: role.get(a[k], a[k]) if k == "causal_parent_action_id" else a[k] for k in
            ("actor_id", "intent", "composition_id", "grant_id", "causal_parent_action_id", "status", "budget", "consumed_budget", "error")} for a in trace["actions"]],
        "invocations": [{k: i[k] for k in ("kind", "target", "attempt", "status", "output_artifact_id", "error", "usage")} for i in execution["invocations"]],
        "events": [{k: role.get(e[k], e[k]) for k in ("entity_type", "entity_id", "event_type", "schema_version", "action_id", "old_status", "new_status", "reason_code")} for e in trace["events"]],
        "projections": [{"manifest": {k: v for k, v in p["manifest"].items() if not k.startswith("x_") and k not in ("projection_id", "meta_revision")},
            "rendered_artifact_id": p["rendered_artifact_id"]} for p in execution["projections"]],
        "edges": sorted((e["edge_type"], role.get(e["from_id"], e["from_id"]), role.get(e["to_id"], e["to_id"]), role[e["source_fact_id"]]) for e in trace["edges"])}
