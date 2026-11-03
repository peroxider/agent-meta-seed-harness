"""Public owner-process control and consumer Provider observations."""

import asyncio
import json

from agent_meta_runtime.sdk import connect


def probe_events(owner):
    events = []
    for line in owner.output.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if "seed_probe_call" in value:
            events.append(value)
    return events


async def wait_invocations(data_dir, task_id, *, statuses):
    client = await connect(data_dir)
    try:
        end = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < end:
            execution = await client.get_task_execution(task_id)
            if [item["status"] for item in execution["invocations"]] == statuses:
                return execution
            if execution["status"] not in ("ACCEPTED", "RUNNING"):
                raise AssertionError(f"Task ended before the requested crash boundary: {execution}")
            await asyncio.sleep(.005)
        raise AssertionError(f"Invocation boundary was not observed: {execution}")
    finally:
        await client.aclose()


async def terminal_execution(data_dir, task_id):
    client = await connect(data_dir)
    try:
        result, terminal = await client.wait_task(task_id, timeout_s=10)
        assert terminal, result
        return result, await client.get_task_execution(task_id)
    finally:
        await client.aclose()
