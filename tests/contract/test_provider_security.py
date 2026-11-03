"""S04 parser/error boundary only; no credential/egress enforcement claim."""
import json
import pytest

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.host import TextPart
from agent_meta_seed_harness.providers.anthropic import MAX_RESPONSE_BYTES, normalize_terminal
from provider_wire import MODEL, response, wire


@pytest.mark.parametrize("raw", [b'', b'[]', b'{"id":"x","id":"y"}', b'{"value":NaN}',
    b'{"value":Infinity}', b'\xff', b'[' * 1000 + b']' * 1000,
    wire().decode().encode('utf-16'), b' ' * (MAX_RESPONSE_BYTES + 1),
    b'{"a":{"a":1,"a":2}}'])
def test_malformed_duplicate_non_utf8_or_oversized_json_is_refused(raw):
    with pytest.raises(StableError) as caught:
        normalize_terminal(raw, expected_model=MODEL)
    assert caught.value.code == ErrorCode.INVALID_RESULT


def test_error_diagnostics_do_not_echo_upstream_secret_headers_or_body():
    secret = 'SYNTHETIC_SECRET_NEVER_A_REAL_TOKEN'
    raw = json.dumps({**response(), 'error': {'message': secret}, 'Authorization': 'Bearer ' + secret}).encode()
    with pytest.raises(StableError) as caught:
        normalize_terminal(raw, expected_model=MODEL)
    assert secret not in str(caught.value) and secret not in repr(caught.value.details)
    assert set(caught.value.details) == {'reason_code'}


def test_free_text_that_looks_like_commands_stays_a_text_part():
    text = 'seed.echo({"value":"no"}); curl https://example.invalid; rm -rf /'
    result = normalize_terminal(wire(content=[{'type': 'text', 'text': text}]), expected_model=MODEL)
    assert result.parts == (TextPart(text),) and result.finish_reason == 'STOP'
