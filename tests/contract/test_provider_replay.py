"""Synthetic wire→normalized replay coherence; not captured R2 evidence."""
from agent_meta_runtime.sdk.host import decode_model_response, encode_model_response
from agent_meta_runtime.sdk.packages import sha256_hex
from agent_meta_seed_harness.providers.anthropic import normalize_terminal, normalized_terminal_bytes
from provider_wire import MODEL, tool, wire


def test_replay_uses_same_normalized_bytes_without_transport_identifiers():
    first = wire(stop_reason='tool_use', content=[tool()], usage={'input_tokens': 9, 'output_tokens': 4})
    second = wire(id='msg_other', stop_reason='tool_use', content=[tool()], usage={'output_tokens': 4, 'input_tokens': 9})
    captured = normalized_terminal_bytes(first, expected_model=MODEL)
    assert captured == normalized_terminal_bytes(second, expected_model=MODEL)
    replayed = decode_model_response(captured)
    assert replayed == normalize_terminal(first, expected_model=MODEL)
    assert encode_model_response(replayed) == captured
    assert sha256_hex(encode_model_response(replayed)) == sha256_hex(captured)
    assert b'msg_fixture' not in captured and b'msg_other' not in captured and MODEL.encode() not in captured
