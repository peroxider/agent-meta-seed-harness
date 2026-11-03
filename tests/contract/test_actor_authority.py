"""SH-HOST-01: initiating actors use their own keys and attenuated grants."""

import asyncio
import json
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from agent_meta_runtime.sdk import CommandAuthority, ErrorCode, StableError, connect
from agent_meta_runtime.sdk.packages import canonical_json

from recovery_runtime import probe_events, terminal_execution
from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import admin, daemon_process


LOOP = b'''
import asyncio
import json
from agent_meta_runtime.sdk.host import ToolCallPart, terminal_result
from agent_meta_runtime.sdk.packages import canonical_json
from .context import project

async def run_task(task, host):
    scenario = json.loads(task.input_content)["scenario"]
    projection = await project(task, host)
    if scenario == "before_model":
        print(canonical_json({"seed_probe_call": "boundary", "phase": "before_model", "task_id": task.task_id}).decode(), flush=True)
        await asyncio.sleep(3)
    response = await host.invoke_model(projection)
    calls = [part for part in response.parts if isinstance(part, ToolCallPart)]
    if calls:
        if scenario == "before_tool":
            print(canonical_json({"seed_probe_call": "boundary", "phase": "before_tool", "task_id": task.task_id}).decode(), flush=True)
            await asyncio.sleep(3)
        for call in calls:
            await host.invoke_tool(call)
        response = await host.invoke_model(projection)
    return terminal_result(response)
'''

PROVIDER = b'''
import json
from agent_meta_runtime.sdk.context import rendered_sections
from agent_meta_runtime.sdk.host import ModelResponse, ProviderUsage, TextPart, ToolCallPart
from agent_meta_runtime.sdk.packages import canonical_json

async def invoke_fake(request):
    print(canonical_json({"seed_probe_call": "model", "task_id": request.task.task_id}).decode(), flush=True)
    scenario = json.loads(rendered_sections(request.projection)["task_input"])["scenario"]
    if scenario in ("tool", "before_tool") and not json.loads(request.history_content):
        return ModelResponse((ToolCallPart("echo", "seed.echo", '{"value":"authorized"}'),), "TOOL_CALL", ProviderUsage(None, None, 0))
    return ModelResponse((TextPart("authorized"),), "STOP", ProviderUsage(None, None, 0))
'''

TOOL = b'''
import json
from agent_meta_runtime.sdk.host import InvocationResult
from agent_meta_runtime.sdk.packages import canonical_json

async def echo(request):
    print(canonical_json({"seed_probe_call": "tool", "task_id": request.task.task_id}).decode(), flush=True)
    return InvocationResult(content=canonical_json({"value": json.loads(request.call.arguments_json)["value"]}))
'''


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    root = tmp_path_factory.mktemp("actor-authority")
    bundle, publisher = seed_bundle(overrides={"agent_meta_seed_harness/loop.py": LOOP,
        "agent_meta_seed_harness/providers/fake.py": PROVIDER, "agent_meta_seed_harness/capabilities/echo.py": TOOL})
    with daemon_process(root, publishers=[publisher]) as owner:
        install_seed(owner.data_dir, root, bundle)
        asyncio.run(wait_ready(owner.data_dir))
        yield owner, root


def principal(runtime):
    owner, _ = runtime
    key = Ed25519PrivateKey.generate()
    identity = admin(owner.data_dir, "authority", "create-principal", "--kind", "AGENT",
        "--public-key-hex", key.public_key().public_bytes_raw().hex())
    assert identity["status"] == "ACTIVE" and identity["public_identity"]["public_key_hex"] == key.public_key().public_bytes_raw().hex()
    return identity["principal_id"], key


def grant(runtime, subject, permissions, *, target=None, constraints=None, delegable=False):
    owner, _ = runtime
    scope = {"realm_id": "realm://main", "targets": [target or {"type": "REALM_ALL"}]}
    flags = [value for permission in permissions for value in ("--permission", permission)]
    return admin(owner.data_dir, "authority", "delegate", "--subject", subject, *flags,
        "--scope", canonical_json(scope).decode(), "--constraints", canonical_json(constraints or {}).decode(),
        *(["--delegable"] if delegable else []))


def input_artifact(runtime, scenario):
    owner, root = runtime
    path = root / "actor-input.json"
    path.write_bytes(canonical_json({"provider": "fake", "scenario": scenario, "value": "fixture"}))
    return admin(owner.data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]


def submit(runtime, subject, key, submission_grant, scenario):
    owner, _ = runtime
    reference = input_artifact(runtime, scenario)
    async def call():
        client = await connect(owner.data_dir, authority=CommandAuthority(subject, submission_grant["grant_id"], key.sign))
        try:
            return await client.submit_task(realm_id="realm://main", actor_id=subject, input_artifact_id=reference)
        finally:
            await client.aclose()
    return asyncio.run(call()).task_id


def observed(runtime, task_id, kind):
    return [item for item in probe_events(runtime[0]) if item.get("task_id") == task_id and item["seed_probe_call"] == kind]


def wait_boundary(runtime, task_id, phase):
    end = time.monotonic() + 10
    while time.monotonic() < end:
        if any(item["phase"] == phase for item in observed(runtime, task_id, "boundary")):
            return
        time.sleep(.01)
    raise AssertionError("consumer scheduling boundary was not observed")


MODEL = {"type": "CAPABILITY", "id": "capability://seed.fake-model"}
ECHO = {"type": "CAPABILITY", "id": "capability://seed.echo"}


@pytest.mark.parametrize("case", ["missing", "wrong_scope", "exhausted", "expired"])
def test_missing_actor_model_authority_cannot_borrow_root_or_harness_service(runtime, case):
    actor, key = principal(runtime)
    submission = grant(runtime, actor, ["task.submit"])
    grant(runtime, actor, ["capability.invoke"], target=ECHO)
    if case != "missing":
        grant(runtime, actor, ["model.invoke"], target=ECHO if case == "wrong_scope" else MODEL,
            constraints={"max_uses": 0} if case == "exhausted" else {"expires_at_us": 1} if case == "expired" else {})
    task_id = submit(runtime, actor, key, submission, "terminal")
    result, execution = asyncio.run(terminal_execution(runtime[0].data_dir, task_id))
    assert result["status"] == "FAILED" and result["error"] == "AUTHORITY_DENIED", result
    assert execution["invocations"] == [] and execution["consumed_budget"] == {}
    assert len(execution["projections"]) == 1
    assert observed(runtime, task_id, "model") == observed(runtime, task_id, "tool") == []


@pytest.mark.parametrize("authorized", [False, True])
def test_frozen_surface_and_context_selection_respect_actor_tool_authority(runtime, authorized):
    actor, key = principal(runtime)
    submission = grant(runtime, actor, ["task.submit"])
    grant(runtime, actor, ["model.invoke"], target=MODEL)
    if authorized:
        grant(runtime, actor, ["capability.invoke"], target=ECHO)
    task_id = submit(runtime, actor, key, submission, "tool")
    result, execution = asyncio.run(terminal_execution(runtime[0].data_dir, task_id))
    if authorized:
        assert result["status"] == "SUCCEEDED", result
        assert [item["kind"] for item in execution["invocations"]] == ["MODEL", "CAPABILITY", "MODEL"]
        assert len(observed(runtime, task_id, "model")) == 2 and len(observed(runtime, task_id, "tool")) == 1
    else:
        assert result["status"] == "FAILED" and result["error"] == "AUTHORITY_DENIED", result
        # Seed's policy explicitly selects echo's schema. With no initiating
        # actor echo grant, the frozen Surface removes it and Context refuses
        # the selection before dispatching even the authorized model.
        assert execution["invocations"] == execution["projections"] == [] and execution["consumed_budget"] == {}
        assert observed(runtime, task_id, "model") == observed(runtime, task_id, "tool") == []
        content = admin(runtime[0].data_dir, "artifact", "content", execution["capability_surface_artifact_id"])
        surface = json.loads(bytes.fromhex(content["content_hex"]))
        operations = {item["operation_id"] for item in surface["operations"]}
        assert "seed.fake-model" in operations and "seed.echo" not in operations


@pytest.mark.parametrize("kind", ["model", "tool"])
def test_actor_revocation_between_projection_model_and_tool_is_immediate(runtime, kind):
    actor, key = principal(runtime)
    submission = grant(runtime, actor, ["task.submit"])
    model = grant(runtime, actor, ["model.invoke"], target=MODEL)
    tool = grant(runtime, actor, ["capability.invoke"], target=ECHO)
    task_id = submit(runtime, actor, key, submission, "before_" + kind)
    wait_boundary(runtime, task_id, "before_" + kind)
    before = admin(runtime[0].data_dir, "task", "execution", task_id)
    revoked = admin(runtime[0].data_dir, "authority", "revoke", (model if kind == "model" else tool)["grant_id"])
    assert revoked["status"] == "REVOKED"
    result, after = asyncio.run(terminal_execution(runtime[0].data_dir, task_id))
    assert result["status"] == "FAILED" and result["error"] == "AUTHORITY_DENIED", result
    assert after["invocations"] == before["invocations"] and after["consumed_budget"] == before["consumed_budget"]
    assert after["projections"] == before["projections"]
    assert len(observed(runtime, task_id, "model")) == int(kind == "tool")
    assert observed(runtime, task_id, "tool") == []


def test_public_delegation_uses_exact_parent_once_and_refuses_another_command(runtime):
    actor, key = principal(runtime)
    child, _ = principal(runtime)
    parent = grant(runtime, actor, ["authority.delegate", "model.invoke"], target=MODEL,
        constraints={"max_uses": 1}, delegable=True)
    async def scenario():
        client = await connect(runtime[0].data_dir, authority=CommandAuthority(actor, parent["grant_id"], key.sign))
        try:
            payload = {"subject_id": child, "permissions": ["model.invoke"],
                "scope": {"realm_id": "realm://main", "targets": [MODEL]}, "constraints": {"max_uses": 1}}
            envelope = client.build_envelope_jcs(realm_id="realm://main", actor_id=actor, payload_type="authority.delegate/v1", payload=payload)
            result = await client.execute_command("agent_meta.public.v1.Authority.Delegate", envelope)
            assert result.resource["parent_grant_id"] == parent["grant_id"] and result.resource["subject_id"] == child
            assert await client.execute_command("agent_meta.public.v1.Authority.Delegate", envelope) == result
            with pytest.raises(StableError) as error:
                await client.delegate_authority(realm_id="realm://main", actor_id=actor, subject_id=child,
                    permissions=["model.invoke"], scope=payload["scope"], constraints=payload["constraints"])
            assert error.value.code == ErrorCode.AUTHORITY_DENIED
        finally:
            await client.aclose()
    asyncio.run(scenario())
