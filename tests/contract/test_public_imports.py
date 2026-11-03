"""S01A consumer compile preparation; bound Host/recovery gates remain open."""

from agent_meta_runtime.sdk import (
    AgentMetaClient, CommandAuthority, ErrorCode, LocalTransport, StableError, connect,
    decode_command, encode_command, sign_command,
)
from agent_meta_runtime.sdk.host import (
    ContextProjection, HarnessAdapter, HealthProbeInvocation, HealthStatus, InvocationResult, ModelResponse,
    ProjectionInput, TaskEnvelope, TaskRuntime, TerminalResult, TextPart,
    decode_model_response, encode_model_response,
)
from agent_meta_runtime.sdk.packages import PackageMeta


def test_public_consumer_symbols_exist_without_private_imports():
    assert all(callable(value) for value in (
        AgentMetaClient, CommandAuthority, LocalTransport, connect, ContextProjection,
        HarnessAdapter, HealthProbeInvocation, HealthStatus, InvocationResult, ProjectionInput, TaskEnvelope,
        TaskRuntime, TerminalResult, PackageMeta, decode_command, encode_command, sign_command,
        AgentMetaClient.prepare_harness_activation,
    ))
    error = StableError(code=ErrorCode.INVALID_RESULT, message="invalid")
    assert error.code == ErrorCode.INVALID_RESULT


def test_normalized_response_roundtrip_uses_public_contract():
    raw = encode_model_response(ModelResponse((TextPart("public consumer"),), "STOP"))
    assert encode_model_response(decode_model_response(raw)) == raw
