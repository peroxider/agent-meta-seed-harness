"""Independent Seed package -> installed public Host -> real Scratch worker."""

import asyncio
import json
import time

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.packages import canonical_json, decode_package, sha256_hex
from toolset_runtime import REALM, tools_environment, submit_tools
from scratch_runtime import prior, published


def test_seed_scratch_full_public_sequence_and_source_only_candidate(tmp_path):
    with tools_environment(tmp_path) as (owner, actor, _, _):

        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:

                async def upload(value):
                    return (
                        await client.put_artifact(
                            realm_id=REALM,
                            actor_id=actor.actor_id,
                            kind="seed_scratch_input",
                            media_type="application/json",
                            content=canonical_json(value),
                        )
                    )["artifact_id"]

                schema = await upload(
                    {"type": "integer", "minimum": 0, "maximum": 1000}
                )
                contract = await upload(
                    {
                        "schema": "capability-contract/v1",
                        "capability_id": "capability://seed-exported",
                        "contract_version": "1.0.0",
                        "operations": [
                            {
                                "operation_id": "apply",
                                "input_schema_artifact_id": schema,
                                "output_schema_artifact_id": schema,
                                "idempotency": "PURE",
                                "retry_semantics": "NEVER",
                                "effects": ["none"],
                                "required_permissions": ["capability.invoke"],
                            }
                        ],
                        "requires": [],
                        "provides": [],
                        "state": {},
                        "execution_requirements": {},
                        "runtime_constraints": {},
                    }
                )
                lock = await upload(
                    {
                        "schema": "scratch-python-dependency-lock/v1",
                        "python_abi": "cp312",
                        "stdlib_modules": [],
                        "wheels": [],
                    }
                )
                source = b'class Box: pass\nvalue=Box()\nvalue.__dict__["password"]="SEED_SCRATCH_CANARY"\nvalue.answer=42\ndef chosen(number):\n    return number+1\nprint("SEED_SCRATCH_READY")\n'
                source_id = (
                    await client.put_artifact(
                        realm_id=REALM,
                        actor_id=actor.actor_id,
                        kind="seed_scratch_source",
                        media_type="text/x-python",
                        content=source,
                    )
                )["artifact_id"]
                session = prior(0, "session_id")
                calls = [
                    {"name": "seed.scratch.create", "arguments": {}},
                    {
                        "name": "seed.scratch.execute",
                        "arguments": {
                            "session_id": session,
                            "source_artifact_id": source_id,
                            "deadline_at_us": time.time_ns() // 1000 + 120000000,
                        },
                    },
                    {
                        "name": "seed.scratch.bindings",
                        "arguments": {"session_id": session},
                    },
                    {
                        "name": "seed.scratch.inspect",
                        "arguments": {"session_id": session, "name": "value"},
                    },
                    {
                        "name": "seed.scratch.export_candidate",
                        "arguments": {
                            "session_id": session,
                            "source_artifact_ids": [source_id],
                            "export_names": ["chosen"],
                            "contract_artifact_id": contract,
                            "dependency_lock_artifact_id": lock,
                            "support_artifact_ids": [schema],
                            "entrypoint": "scratch_candidate:chosen",
                        },
                    },
                    {
                        "name": "seed.artifact.read",
                        "arguments": {"artifact_id": prior(1, "stdout_artifact_id")},
                    },
                    {
                        "name": "seed.scratch.release",
                        "arguments": {"session_id": session},
                    },
                ]
                task, terminal, execution = await submit_tools(
                    client, actor, calls, scenario="sequence"
                )
                assert terminal["status"] == "SUCCEEDED", terminal
                values = await published(client, execution)
                assert len(values) == 7 and values[-1]["status"] == "RELEASED"
                assert values[1]["cell_ordinal"] == values[1]["execution_count"] == 1
                tools = [
                    row
                    for row in execution["invocations"]
                    if row["kind"] == "CAPABILITY"
                ]
                binding = next(
                    item for item in values[2]["bindings"] if item["name"] == "value"
                )
                assert binding["source_artifact_id"] == source_id
                assert (
                    binding["created_by_action_id"]
                    == binding["last_cell_action_id"]
                    == tools[1]["action_id"]
                )
                assert values[3]["observed_by_action_id"] == tools[3]["action_id"]
                assert "SEED_SCRATCH_CANARY" not in str(values)
                assert values[5]["content"]["value"]["text"] == "SEED_SCRATCH_READY\n"
                candidate = values[4]
                assert (
                    candidate["trust_class"] == "trusted_candidate"
                    and candidate["experiment_promotion_required"]
                )
                assert (
                    not candidate["serving_changed"]
                    and candidate["exported_by_action_id"] == tools[4]["action_id"]
                )
                package = await client.get_artifact_content(
                    candidate["package_artifact_id"]
                )
                assert candidate[
                    "package_artifact_id"
                ] == "artifact://sha256/" + sha256_hex(package)
                manifest, source_files = decode_package(package)
                assert (
                    source_files["scratch_candidate.py"]
                    == b"def chosen(number):\n    return number+1\n"
                )
                assert (
                    manifest.package.runtime_constraints["trust_class"]
                    == "trusted_candidate"
                )
                trace = await client.get_task_trace(task.task_id)
                assert any(
                    edge["edge_type"] == "produced"
                    and edge["from_id"] == tools[4]["invocation_id"]
                    and edge["to_id"] == candidate["package_artifact_id"]
                    for edge in trace["edges"]
                )
                assert (await client.get_view())["serving_revision"] == 1
                _, expired, _ = await submit_tools(
                    client,
                    actor,
                    [
                        {
                            "name": "seed.scratch.inspect",
                            "arguments": {
                                "session_id": values[0]["session_id"],
                                "handle": binding["handle"],
                            },
                        }
                    ],
                )
                assert expired["error"] == "HANDLE_EXPIRED", expired
            finally:
                await client.aclose()

        asyncio.run(run())


@pytest.mark.parametrize(
    "target,expected",
    [
        ({"name": "value.__dict__"}, "INVALID_RESULT"),
        ({"handle": "obs:unissued"}, "HANDLE_EXPIRED"),
    ],
)
def test_seed_inspection_refuses_expressions_and_unissued_handles(
    tmp_path, target, expected
):
    with tools_environment(tmp_path) as (owner, actor, _, _):

        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                _, terminal, created = await submit_tools(
                    client, actor, [{"name": "seed.scratch.create", "arguments": {}}]
                )
                assert terminal["status"] == "SUCCEEDED", terminal
                session = (await published(client, created))[0]["session_id"]
                _, denied, _ = await submit_tools(
                    client,
                    actor,
                    [
                        {
                            "name": "seed.scratch.inspect",
                            "arguments": {"session_id": session, **target},
                        }
                    ],
                )
                assert denied["error"] == expected, denied
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
            finally:
                await client.aclose()

        asyncio.run(run())


def test_scratch_output_channels_mark_truncation_explicitly_and_keep_schema(tmp_path):
    with tools_environment(tmp_path) as (owner, actor, _, _):

        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                small_source = await client.put_artifact(
                    realm_id=REALM,
                    actor_id=actor.actor_id,
                    kind="seed_scratch_source",
                    media_type="text/x-python",
                    content=b'print("SEED_TRUNC_SMALL")\n',
                )
                large_source = await client.put_artifact(
                    realm_id=REALM,
                    actor_id=actor.actor_id,
                    kind="seed_scratch_source",
                    media_type="text/x-python",
                    content=b'import sys\nsys.stdout.write("x"*(1024*1024+4096))\nprint("SEED_TRUNC_READY")\n',
                )
                session = prior(0, "session_id")

                def cell(reference):
                    return {
                        "name": "seed.scratch.execute",
                        "arguments": {
                            "session_id": session,
                            "source_artifact_id": reference["artifact_id"],
                            "deadline_at_us": time.time_ns() // 1000 + 120000000,
                        },
                    }

                task, terminal, execution = await submit_tools(
                    client,
                    actor,
                    [
                        {"name": "seed.scratch.create", "arguments": {}},
                        cell(small_source),
                        cell(large_source),
                    ],
                    scenario="sequence",
                )
                assert terminal["status"] == "SUCCEEDED", terminal
                values = await published(client, execution)
                small, large = values[1], values[2]
                # One cell prints a small line; the next exceeds the channel
                # cap, and only the oversized channel is explicitly marked.
                assert small["schema"] == "scratch-execution-receipt/v1"
                assert small["stdout_truncated"] is False
                assert large["schema"] == "scratch-execution-receipt/v1"
                assert large["stdout_truncated"] is True
                assert large["stderr_truncated"] is False
                assert large["display_truncated"] is False
                stream = json.loads(
                    await client.get_artifact_content(large["stdout_artifact_id"])
                )
                assert stream["schema"] == "scratch-stream/v1"
                assert stream["channel"] == "stdout"
                assert stream["session_id"] == small["session_id"] == large["session_id"]
                # The staged channel stays inside the 1 MiB output ceiling
                # while the receipt keeps its full documented shape.
                assert len(stream["text"].encode("utf-8")) <= 1024 * 1024
                assert stream["text"].startswith("x" * 1024)
                small_stream = json.loads(
                    await client.get_artifact_content(small["stdout_artifact_id"])
                )
                assert small_stream["text"] == "SEED_TRUNC_SMALL\n"
            finally:
                await client.aclose()

        asyncio.run(run())
