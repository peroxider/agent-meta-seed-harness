"""Public-only native cancellation and actual daemon-loss Scratch recovery."""

import asyncio
import json
import time

from agent_meta_runtime.sdk import connect
from seed_package import seed_bundle
from seed_runtime import daemon_process
from toolset_runtime import REALM, PERMISSIONS, tools_environment, submit_tools, upload
from scratch_runtime import prior, published


async def source(client, actor, content):
    return (
        await client.put_artifact(
            realm_id=REALM,
            actor_id=actor.actor_id,
            kind="seed_scratch_source",
            media_type="text/x-python",
            content=content,
        )
    )["artifact_id"]


def test_seed_cancel_interrupts_real_cell_and_keeps_observed_heap_usable(tmp_path):
    with tools_environment(
        tmp_path, actor_permissions=[*PERMISSIONS, "task.cancel"]
    ) as (owner, actor, _, _):

        async def run():
            client = await connect(owner.data_dir, authority=actor)
            control = await connect(owner.data_dir, authority=actor)
            pending = None
            try:
                _, created, execution = await submit_tools(
                    client, actor, [{"name": "seed.scratch.create", "arguments": {}}]
                )
                assert created["status"] == "SUCCEEDED", created
                session = (await published(client, execution))[0]["session_id"]
                reference = await source(
                    client, actor, b"entered=True\nwhile True: pass\n"
                )
                task_input = await upload(
                    client,
                    actor,
                    {
                        "provider": "fake-tools",
                        "calls": [
                            {
                                "name": "seed.scratch.execute",
                                "arguments": {
                                    "session_id": session,
                                    "source_artifact_id": reference,
                                    "deadline_at_us": time.time_ns() // 1000 + 30000000,
                                },
                            }
                        ],
                    },
                    "task_input",
                )
                task = await client.submit_task(
                    realm_id=REALM,
                    actor_id=actor.actor_id,
                    input_artifact_id=task_input,
                )
                async with asyncio.timeout(10):
                    while True:
                        trace = await control.get_task_trace(task.task_id)
                        if any(
                            event["event_type"] == "scratch_dispatch_authorized"
                            for event in trace["events"]
                        ):
                            break
                        await asyncio.sleep(0.02)
                await asyncio.sleep(0.1)
                pending = asyncio.create_task(
                    client.wait_task(task.task_id, timeout_s=15)
                )
                started = time.monotonic()
                await control.cancel_task(
                    realm_id=REALM, actor_id=actor.actor_id, task_id=task.task_id
                )
                cancelled, done = await pending
                assert done and cancelled["status"] == "CANCELLED", cancelled
                assert time.monotonic() - started < 10
                # A separate safe read proves the actual user cell entered and
                # the interrupted kernel remained usable. No workspace/DB read.
                _, inspected, observation = await submit_tools(
                    control,
                    actor,
                    [
                        {
                            "name": "seed.scratch.inspect",
                            "arguments": {"session_id": session, "name": "entered"},
                        }
                    ],
                )
                assert inspected["status"] == "SUCCEEDED", inspected
                value = (await published(control, observation))[0]
                assert value["cell_ordinal"] == 1 and value["node"]["value"] is True
                assert value["binding_origin"]["source_artifact_id"] == reference
                _, released, _ = await submit_tools(
                    control,
                    actor,
                    [
                        {
                            "name": "seed.scratch.release",
                            "arguments": {"session_id": session},
                        }
                    ],
                )
                assert released["status"] == "SUCCEEDED", released
            finally:
                if pending is not None:
                    if not pending.done():
                        pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                await control.aclose()
                await client.aclose()

        asyncio.run(run())


def test_seed_daemon_kill_expires_handles_and_never_adopts_prior_heap(tmp_path):
    with tools_environment(tmp_path) as (owner, actor, _, _):

        async def initialize():
            client = await connect(owner.data_dir, authority=actor)
            try:
                reference = await source(
                    client, actor, b"class Box: pass\nvalue=Box()\nvalue.number=42\n"
                )
                task, terminal, execution = await submit_tools(
                    client,
                    actor,
                    [
                        {"name": "seed.scratch.create", "arguments": {}},
                        {
                            "name": "seed.scratch.execute",
                            "arguments": {
                                "session_id": prior(0, "session_id"),
                                "source_artifact_id": reference,
                                "deadline_at_us": time.time_ns() // 1000 + 30000000,
                            },
                        },
                        {
                            "name": "seed.scratch.bindings",
                            "arguments": {"session_id": prior(0, "session_id")},
                        },
                    ],
                    scenario="sequence",
                )
                assert terminal["status"] == "SUCCEEDED", terminal
                values = await published(client, execution)
                handle = next(
                    item["handle"]
                    for item in values[2]["bindings"]
                    if item["name"] == "value"
                )
                return (
                    task.task_id,
                    execution["invocations"],
                    values[0]["session_id"],
                    handle,
                )
            finally:
                await client.aclose()

        task, confirmed, session, handle = asyncio.run(initialize())
        owner.process.kill()
        owner.process.wait(timeout=10)
    _, publisher = seed_bundle(tools=True)
    with daemon_process(
        tmp_path, publishers=[publisher], label="scratch-recovered"
    ) as recovered:

        async def inspect():
            client = await connect(recovered.data_dir, authority=actor)
            try:
                prior_execution = await client.get_task_execution(task)
                assert prior_execution["invocations"] == confirmed
                _, lost, _ = await submit_tools(
                    client,
                    actor,
                    [
                        {
                            "name": "seed.scratch.inspect",
                            "arguments": {"session_id": session, "handle": handle},
                        }
                    ],
                )
                assert lost["error"] == "HANDLE_EXPIRED", lost
                _, released, _ = await submit_tools(
                    client,
                    actor,
                    [
                        {
                            "name": "seed.scratch.release",
                            "arguments": {"session_id": session},
                        }
                    ],
                )
                assert released["status"] == "SUCCEEDED", released
                _, fresh, execution = await submit_tools(
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
                assert fresh["status"] == "SUCCEEDED", fresh
                values = await published(client, execution)
                assert values[0]["session_id"] != session
                assert values[1]["cell_ordinal"] == 0 and values[1]["bindings"] == []
            finally:
                await client.aclose()

        asyncio.run(inspect())
