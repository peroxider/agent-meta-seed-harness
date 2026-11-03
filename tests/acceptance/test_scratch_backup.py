"""Independent public backup/native restore; no DB/CAS/key/workspace reads."""

import asyncio
import json
import os
import subprocess
import sys
import time

from agent_meta_runtime.sdk import connect
from seed_package import seed_bundle, wait_ready
from seed_runtime import admin, daemon_process, invoke
from scratch_runtime import prior, published
from toolset_runtime import REALM, tools_environment, submit_tools


RESTORE = "import importlib.metadata as m; import sys; e=next(e for e in m.distribution('agent-meta-runtime').entry_points if e.group=='console_scripts' and e.name=='agent-meta-restore'); sys.exit(e.load()())"


def test_seed_live_scratch_blocks_backup_then_released_history_restores_without_heap(
    tmp_path,
):
    backup = tmp_path / "released-backup"
    with tools_environment(tmp_path) as (owner, actor, _, _):

        async def prepare():
            client = await connect(owner.data_dir, authority=actor)
            try:
                source = (
                    await client.put_artifact(
                        realm_id=REALM,
                        actor_id=actor.actor_id,
                        kind="seed_scratch_source",
                        media_type="text/x-python",
                        content=b"class Box: pass\nvalue=Box()\nvalue.number=42\n",
                    )
                )["artifact_id"]
                task, terminal, execution = await submit_tools(
                    client,
                    actor,
                    [
                        {"name": "seed.scratch.create", "arguments": {}},
                        {
                            "name": "seed.scratch.execute",
                            "arguments": {
                                "session_id": prior(0, "session_id"),
                                "source_artifact_id": source,
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
                session = values[0]["session_id"]
                handle = next(
                    item["handle"]
                    for item in values[2]["bindings"]
                    if item["name"] == "value"
                )
                denied_destination = tmp_path / "live-backup"
                rejected, denied = await asyncio.to_thread(
                    invoke,
                    owner.data_dir,
                    "operations",
                    "backup",
                    "--destination",
                    str(denied_destination),
                )
                assert rejected.returncode == 6 and not denied["ok"], denied
                assert denied["error"]["code"] == "FAILED_PRECONDITION"
                assert denied["error"]["details"]["problems"] == ["LIVE_SCRATCH"]
                assert not denied_destination.exists()
                release_task, released, _ = await submit_tools(
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
                trace = await client.get_task_trace(release_task.task_id)
                assert any(
                    event["event_type"] == "workspace_cleanup_completed"
                    for event in trace["events"]
                )
                accepted = await asyncio.to_thread(
                    admin,
                    owner.data_dir,
                    "operations",
                    "backup",
                    "--destination",
                    str(backup),
                )
                result = await client.wait_operation(
                    accepted["operation_id"], timeout_s=20
                )
                assert result["status"] == "SUCCEEDED", result
                # This is the explicit operator backup output, not live storage.
                manifest = json.loads((backup / "backup-manifest.json").read_bytes())
                assert all(
                    entry["relpath"] == "meta.db"
                    or entry["relpath"].split("/")[0]
                    in ("artifacts", "keys", "backend")
                    for entry in manifest["files"]
                )
                assert not any(
                    entry["relpath"].startswith(("workspaces/", "workspace/", "run/"))
                    for entry in manifest["files"]
                )
                return (
                    task.task_id,
                    execution["invocations"],
                    session,
                    handle,
                    accepted["operation_id"],
                    manifest,
                )
            finally:
                await client.aclose()

        task_id, confirmed, old_session, old_handle, backup_operation, manifest = (
            asyncio.run(prepare())
        )

    restored_root = tmp_path / "restored-runtime"
    restored_data = restored_root / "data"
    flags = ["--insecure-dev-credential-file"] if os.name != "nt" else []
    process = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            RESTORE,
            "--source",
            str(backup),
            "--data-dir",
            str(restored_data),
            *flags,
        ],
        capture_output=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    restored = json.loads(process.stdout)
    assert process.returncode == 0 and restored["ok"], (restored, process.stderr)
    assert restored["result"]["realm_id"] == manifest["realm_id"]
    assert restored["result"]["epoch_id"] == manifest["epoch_id"]
    assert restored["result"]["meta_revision"] == manifest["meta_revision"]
    assert restored["result"]["quarantined_operations"] >= 1
    _, publisher = seed_bundle(tools=True)
    with daemon_process(
        restored_root, publishers=[publisher], label="restored-scratch"
    ) as recovered:

        async def inspect():
            await wait_ready(recovered.data_dir)
            client = await connect(recovered.data_dir, authority=actor)
            try:
                execution = await client.get_task_execution(task_id)
                assert execution["invocations"] == confirmed
                operation = await client.get_operation(backup_operation)
                assert operation["status"] == "FAILED_RECOVERY", operation
                assert operation["error"]["reason_code"] == "RESTORE_QUARANTINE"
                _, expired, _ = await submit_tools(
                    client,
                    actor,
                    [
                        {
                            "name": "seed.scratch.inspect",
                            "arguments": {
                                "session_id": old_session,
                                "handle": old_handle,
                            },
                        }
                    ],
                )
                assert expired["error"] == "HANDLE_EXPIRED", expired
                _, terminal, fresh = await submit_tools(
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
                values = await published(client, fresh)
                assert values[0]["session_id"] != old_session
                assert values[1]["cell_ordinal"] == 0 and values[1]["bindings"] == []
                assert values[2]["status"] == "RELEASED"
                # Public operator doctor verifies the restored chain and content.
                report = await asyncio.to_thread(admin, recovered.data_dir, "doctor")
                assert report["ok"], report
            finally:
                await client.aclose()

        asyncio.run(inspect())
