"""RP-05 stable command replay at the Task boundary, at envelope level.

A committed Task.Submit response is dropped at the consumer Transport
return boundary and the owned daemon is then killed before the Task
terminal. Recovery replays the exact signed envelope bytes against the
restarted daemon: the same Task identity, the original serving revision,
one durable model call and one unique terminal. A lost Task.Wait
observation re-observes the identical committed resource without any
redispatch. No Runtime implementation, database or private key material
is read.
"""

import asyncio

import pytest

from agent_meta_runtime.sdk import AgentMetaClient, LocalTransport, connect
from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, encode_terminal_result
from agent_meta_runtime.sdk.packages import sha256_hex
from agent_meta_runtime.sdk.transport import LocalConnection

from agent_meta_seed_harness.session_coordinator import message_input, upload

from recovery_runtime import probe_events
from seed_actor import create_actor
from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import daemon_process

REALM = "realm://main"
SUBMIT = "agent_meta.public.v1.Task.Submit"
WAIT = "agent_meta.public.v1.Task.Wait"
SUBMIT_1 = "task://019a44d0-0000-7000-8000-000000000001"
SUBMIT_2 = "task://019a44d0-0000-7000-8000-000000000002"
PERMISSIONS = [
    "artifact.put", "task.submit", "task.cancel", "model.invoke",
    "capability.invoke", "state.read", "state.write",
]

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

# The consumer scheduling window after a durably confirmed model result and
# before the Task terminal makes the crash boundary deterministic.
LOOP = b'''
import asyncio
from agent_meta_runtime.sdk.host import terminal_result
from .context import project

async def run_task(task, host):
    response = await host.invoke_model(await project(task, host))
    await asyncio.sleep(3)
    return terminal_result(response)
'''


def instrumented_bundle():
    return seed_bundle(overrides={
        "agent_meta_seed_harness/providers/fake.py": PROVIDER,
        "agent_meta_seed_harness/loop.py": LOOP,
    })


class DropCommittedResponse:
    """Fault at the consumer Transport return boundary, before SDK decoding.

    The raw wire response is retained by the harness for comparison while
    the SDK caller receives only the fault; the bytes stay opaque here.
    """

    def __init__(self, delegate, *, method):
        self.delegate, self.method = delegate, method
        self.raw = None

    async def call(self, method, request, *, deadline_us=None):
        response = await self.delegate.call(method, request, deadline_us=deadline_us)
        if method == self.method and self.raw is None:
            self.raw = response
            raise ConnectionError("consumer fault: committed response discarded")
        return response

    async def close(self):
        await self.delegate.close()


class CaptureTransport:
    """Passthrough that retains each method's raw wire response."""

    def __init__(self, delegate):
        self.delegate = delegate
        self.raw = {}

    async def call(self, method, request, *, deadline_us=None):
        response = await self.delegate.call(method, request, deadline_us=deadline_us)
        self.raw[method] = response
        return response

    async def close(self):
        await self.delegate.close()


async def await_probe(owner, count):
    end = asyncio.get_running_loop().time() + 10
    while len(probe_events(owner)) < count:
        if asyncio.get_running_loop().time() > end:
            raise AssertionError(f"Provider callbacks were not observed: {probe_events(owner)}")
        await asyncio.sleep(0.005)


def test_lost_submit_response_and_crash_before_terminal_replay_same_task(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="before-loss") as owner:
        install_seed(owner.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(owner.data_dir))
        authority = create_actor(owner.data_dir, permissions=PERMISSIONS)

        async def lose_response():
            connection = LocalConnection(owner.data_dir / "run/agent-meta.sock")
            await connection.connect()
            fault = DropCommittedResponse(LocalTransport(connection), method=SUBMIT)
            client = AgentMetaClient(fault, authority=authority)
            try:
                reference = await upload(client, authority,
                    message_input("canary"), kind="task_input")
                envelope = client.build_envelope_jcs(
                    realm_id=REALM, actor_id=authority.actor_id,
                    payload_type="task.submit/v1",
                    payload={"input_artifact_id": reference}, command_id=SUBMIT_1)
                with pytest.raises(ConnectionError, match="discarded"):
                    await client.execute_command(SUBMIT, envelope)
                # The fault retained the discarded wire response; the SDK
                # caller never saw the receipt or the Task identity.
                assert fault.raw
                return envelope, fault.raw
            finally:
                await client.aclose()

        envelope, dropped = asyncio.run(lose_response())
        # The fake model call completes immediately and the loop then idles
        # three seconds before the terminal, so killing one second after the
        # observed Provider callback lands inside the confirmed-result window.
        async def confirmed_window():
            await await_probe(owner, 1)
            await asyncio.sleep(1.0)

        asyncio.run(confirmed_window())
        calls = probe_events(owner)
        owner.process.kill()
        owner.process.wait(timeout=10)
    with daemon_process(tmp_path, publishers=[publisher], label="after-loss") as recovered:
        async def replay():
            connection = LocalConnection(recovered.data_dir / "run/agent-meta.sock")
            await connection.connect()
            capture = CaptureTransport(LocalTransport(connection))
            client = AgentMetaClient(capture, authority=authority)
            try:
                receipt = await client.execute_command(SUBMIT, envelope)
                task_id = receipt.resource["task_id"]
                assert receipt.resource["serving_revision"] > 0
                # The replayed wire receipt is byte-identical to the discarded
                # one: same Task identity, same serving revision, same receipt.
                assert capture.raw[SUBMIT] == dropped
                assert await client.execute_command(SUBMIT, envelope) == receipt
                result, terminal = await client.wait_task(task_id, timeout_s=15)
                assert terminal and result["status"] == "SUCCEEDED", result
                expected = encode_terminal_result(TerminalResult(
                    (JsonPart({"nonce": calls[0]["nonce"]}),)))
                assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(expected)
                after = await client.get_task_execution(task_id)
                assert after["consumed_budget"]["model_calls"] == 1
                assert len(after["invocations"]) == 1
            finally:
                await client.aclose()

        asyncio.run(replay())
        # No incarnation of the daemon ever dispatched a second model call.
        assert probe_events(recovered) == []


def test_lost_wait_response_reobserves_identical_committed_resource(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="wait-loss") as owner:
        install_seed(owner.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(owner.data_dir))
        authority = create_actor(owner.data_dir, permissions=PERMISSIONS)

        async def run():
            clean = await connect(owner.data_dir, authority=authority)
            try:
                reference = await upload(clean, authority,
                    message_input("canary"), kind="task_input")
                envelope = clean.build_envelope_jcs(
                    realm_id=REALM, actor_id=authority.actor_id,
                    payload_type="task.submit/v1",
                    payload={"input_artifact_id": reference}, command_id=SUBMIT_1)
                receipt = await clean.execute_command(SUBMIT, envelope)
                task_id = receipt.resource["task_id"]
                connection = LocalConnection(owner.data_dir / "run/agent-meta.sock")
                await connection.connect()
                fault = DropCommittedResponse(LocalTransport(connection), method=WAIT)
                observer = AgentMetaClient(fault, authority=authority)
                try:
                    with pytest.raises(ConnectionError, match="discarded"):
                        await observer.wait_task(task_id, timeout_s=10)
                    assert fault.raw
                finally:
                    await observer.aclose()
                # The daemon stays alive; a fresh connection re-observes the
                # byte-identical committed terminal response at the Transport
                # boundary.
                reconnection = LocalConnection(owner.data_dir / "run/agent-meta.sock")
                await reconnection.connect()
                capture = CaptureTransport(LocalTransport(reconnection))
                observer = AgentMetaClient(capture, authority=authority)
                try:
                    result, terminal = await observer.wait_task(task_id, timeout_s=10)
                    assert terminal and result["status"] == "SUCCEEDED", result
                    assert capture.raw[WAIT] == fault.raw
                finally:
                    await observer.aclose()
                # The original submit envelope still replays its receipt.
                assert await clean.execute_command(SUBMIT, envelope) == receipt
                after = await clean.get_task_execution(task_id)
                assert after["consumed_budget"]["model_calls"] == 1
                assert after["serving_revision"] == receipt.resource["serving_revision"]
            finally:
                await clean.aclose()

        asyncio.run(run())
        assert len(probe_events(owner)) == 1


def test_restart_continues_the_frozen_serving_revision_for_new_tasks(tmp_path):
    bundle, publisher = instrumented_bundle()
    with daemon_process(tmp_path, publishers=[publisher], label="first") as owner:
        install_seed(owner.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(owner.data_dir))
        authority = create_actor(owner.data_dir, permissions=PERMISSIONS)

        async def submit(envelope):
            client = await connect(owner.data_dir, authority=authority)
            try:
                receipt = await client.execute_command(SUBMIT, envelope)
                result, terminal = await client.wait_task(
                    receipt.resource["task_id"], timeout_s=15)
                assert terminal and result["status"] == "SUCCEEDED", result
                return envelope, receipt
            finally:
                await client.aclose()

        async def prepare(value, command_id):
            client = await connect(owner.data_dir, authority=authority)
            try:
                reference = await upload(client, authority,
                    message_input(value), kind="task_input")
                return client.build_envelope_jcs(
                    realm_id=REALM, actor_id=authority.actor_id,
                    payload_type="task.submit/v1",
                    payload={"input_artifact_id": reference}, command_id=command_id)
            finally:
                await client.aclose()

        first_envelope = asyncio.run(prepare("first", SUBMIT_1))
        _, first_receipt = asyncio.run(submit(first_envelope))
        serving = first_receipt.resource["serving_revision"]
        assert serving > 0
        assert len(probe_events(owner)) == 1
        owner.process.kill()
        owner.process.wait(timeout=10)
    with daemon_process(tmp_path, publishers=[publisher], label="second") as recovered:
        async def verify():
            client = await connect(recovered.data_dir, authority=authority)
            try:
                # The pre-restart envelope replays its exact durable receipt.
                assert await client.execute_command(SUBMIT, first_envelope) == first_receipt
                # A brand-new post-restart Task keeps serving under the same
                # frozen serving revision: a plain restart does not advance
                # serving; only a reviewed package cutover does.
                reference = await upload(client, authority,
                    message_input("second"), kind="task_input")
                second_envelope = client.build_envelope_jcs(
                    realm_id=REALM, actor_id=authority.actor_id,
                    payload_type="task.submit/v1",
                    payload={"input_artifact_id": reference}, command_id=SUBMIT_2)
                receipt = await client.execute_command(SUBMIT, second_envelope)
                assert receipt.resource["serving_revision"] == serving
                result, terminal = await client.wait_task(
                    receipt.resource["task_id"], timeout_s=15)
                assert terminal and result["status"] == "SUCCEEDED", result
                trace = await client.get_task_trace(receipt.resource["task_id"])
                before = await client.get_task_trace(first_receipt.resource["task_id"])
                assert trace["actions"][0]["composition_id"] == \
                    before["actions"][0]["composition_id"]
            finally:
                await client.aclose()

        asyncio.run(verify())
        assert len(probe_events(recovered)) == 1
