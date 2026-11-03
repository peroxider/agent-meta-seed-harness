"""S04 codec development: synthetic terminal responses, no live claim."""
import pytest

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.host import TextPart, ToolCallPart
from agent_meta_seed_harness.providers.anthropic import normalize_terminal
from provider_wire import MODEL, tool, wire


@pytest.mark.parametrize("reason,stop,expected", [("end_turn", None, "STOP"),
    ("stop_sequence", "END", "STOP"), ("max_tokens", None, "LENGTH")])
def test_complete_text_terminal_mapping_preserves_order(reason, stop, expected):
    result = normalize_terminal(wire(stop_reason=reason, stop_sequence=stop,
        content=[{"type": "text", "text": "first"}, {"type": "text", "text": "last"}]), expected_model=MODEL)
    assert result.finish_reason == expected and result.parts == (TextPart("first"), TextPart("last"))
    assert result.usage.input_tokens is result.usage.output_tokens is result.usage.cost_microunits is None


def test_structured_tool_calls_keep_ids_order_and_canonical_arguments():
    result = normalize_terminal(wire(stop_reason="tool_use", content=[tool(1),
        {"type": "text", "text": "between"}, tool(2)]), expected_model=MODEL)
    assert result.finish_reason == "TOOL_CALL"
    assert result.parts == (ToolCallPart("call_1", "seed.echo", '{"value":"1"}'), TextPart("between"),
        ToolCallPart("call_2", "seed.echo", '{"value":"2"}'))


@pytest.mark.parametrize("usage,expected", [(None, (None, None)), ({}, (None, None)),
    ({"input_tokens": 0, "output_tokens": 0}, (0, 0)),
    ({"input_tokens": 12, "output_tokens": 3, "cache_read_input_tokens": 0}, (12, 3))])
def test_reported_usage_keeps_zero_and_unknown_distinct_without_inventing_cost(usage, expected):
    result = normalize_terminal(wire(usage=usage), expected_model=MODEL)
    assert (result.usage.input_tokens, result.usage.output_tokens) == expected
    assert result.usage.cost_microunits is None


@pytest.mark.parametrize("changes", [
    {"model": "unapproved-alias"}, {"role": "user"}, {"type": "message_start"},
    {"stop_reason": "pause_turn"}, {"stop_reason": None}, {"stop_reason": "refusal"},
    {"stop_reason": "tool_use"}, {"stop_reason": "stop_sequence"}, {"stop_sequence": "unexpected"},
    {"content": []}, {"content": [{"type": "text", "text": ""}]},
    {"content": [tool()]}, {"content": [tool()], "stop_reason": "max_tokens"},
    {"content": [tool(), tool()], "stop_reason": "tool_use"},
    {"content": [tool(i) for i in range(17)], "stop_reason": "tool_use"},
    {"content": [{"type": "thinking", "thinking": "private reasoning"}]},
    {"content": [{"type": "tool_result", "tool_use_id": "call_0", "content": "no"}]},
    {"content": [{"type": "text", "text": "hello", "citations": []}]},
    {"usage": {"input_tokens": True}}, {"usage": {"output_tokens": -1}},
    {"usage": {"input_tokens": 1.5}}, {"usage": {"cache_read_input_tokens": 1}},
    {"usage": {"cache_creation_input_tokens": None}}, {"usage": {"unknown": 0}},
])
def test_unsupported_partial_or_contradictory_responses_fail_before_dispatch(changes):
    with pytest.raises(StableError) as caught:
        normalize_terminal(wire(**changes), expected_model=MODEL)
    assert caught.value.code == ErrorCode.INVALID_RESULT
