"""Public native lifecycle: retirement releases Realm Scratch capacity."""

import asyncio

from agent_meta_runtime.sdk import connect
from seed_package import seed_bundle, activate_seed, wait_ready
from seed_runtime import admin
from scratch_runtime import prior, published
from toolset_runtime import REALM, tools_environment, submit_tools


def test_seed_retirement_releases_scratch_before_ready_and_reactivation(tmp_path):
    with tools_environment(tmp_path) as (owner, actor, _, _):

        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                task, terminal, execution = await submit_tools(
                    client, actor, [{"name": "seed.scratch.create", "arguments": {}}]
                )
                assert terminal["status"] == "SUCCEEDED", terminal
                old_session = (await published(client, execution))[0]["session_id"]
                harness = (await client.list_harnesses(status="ACTIVE"))[0]
                await asyncio.to_thread(
                    admin,
                    owner.data_dir,
                    "harness",
                    "deactivate",
                    harness["harness_id"],
                )
                async with asyncio.timeout(15):
                    while True:
                        refs = await client.get_refs()
                        if (
                            refs["serving_revision"] == 0
                            and refs["reconcile_status"] == "READY"
                        ):
                            break
                        await asyncio.sleep(0.02)
                trace = await client.get_task_trace(task.task_id)
                assert any(
                    event["event_type"] == "workspace_cleanup_completed"
                    for event in trace["events"]
                )
                bundle, _ = seed_bundle(tools=True)
                await asyncio.to_thread(
                    activate_seed, owner.data_dir, bundle, harness["harness_id"]
                )
                await wait_ready(owner.data_dir)
                _, terminal, execution = await submit_tools(
                    client,
                    actor,
                    [
                        {"name": "seed.scratch.create", "arguments": {}},
                        {
                            "name": "seed.scratch.bindings",
                            "arguments": {"session_id": prior(0, "session_id")},
                        },
                        {
                            "name": "seed.scratch.release",
                            "arguments": {"session_id": prior(0, "session_id")},
                        },
                    ],
                    scenario="sequence",
                )
                assert terminal["status"] == "SUCCEEDED", terminal
                values = await published(client, execution)
                assert values[0]["session_id"] != old_session
                assert values[1]["cell_ordinal"] == 0 and values[1]["bindings"] == []
                assert values[2]["status"] == "RELEASED"
            finally:
                await client.aclose()

        asyncio.run(run())
