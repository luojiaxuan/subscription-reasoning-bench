from subscription_reasoning_bench.adapters.claude import ClaudeAdapter
from subscription_reasoning_bench.adapters.codex import CodexAdapter
from subscription_reasoning_bench.models import RunConfig


def test_codex_fast_command_is_explicit():
    command = CodexAdapter("codex").build_command(RunConfig("codex", "gpt-5.6-sol", "xhigh", "fast"))
    assert 'service_tier="fast"' in command
    assert "--ignore-user-config" in command
    assert command[-1] == "-"


def test_codex_standard_does_not_inherit_fast():
    command = CodexAdapter("codex").build_command(RunConfig("codex", "gpt-5.6-sol", "high", "standard"))
    assert command[command.index("--disable") + 1] == "browser_use"
    assert "fast_mode" in command
    assert not any("service_tier" in part for part in command)


def test_codex_trace_parser_counts_process_shape():
    trace = [
        {"type": "thread.started", "model": "gpt-5.6-sol"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "reasoning", "text": "hidden"}},
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "<final_answer>A</final_answer>"},
        },
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 3}},
    ]
    result = CodexAdapter("codex").parse_trace(trace, "", "", 123, 0)
    assert result.status == "ok"
    assert result.native_metrics["native_turns"] == 1
    assert result.native_metrics["reasoning_events"] == 1
    assert result.native_metrics["output_tokens"] == 3


def test_claude_rejects_fake_ultra_effort():
    adapter = ClaudeAdapter()
    try:
        adapter.validate_config(RunConfig("claude", "claude-sonnet-5", "ultra"))
    except ValueError as exc:
        assert "ultracode" in str(exc)
    else:
        raise AssertionError("Claude ultra should not be accepted")


def test_claude_trace_parser_uses_result_turn_count():
    trace = [
        {"type": "system", "subtype": "init", "model": "claude-sonnet-5"},
        {
            "type": "assistant",
            "message": {
                "model": "claude-sonnet-5",
                "content": [{"type": "text", "text": "<final_answer>7</final_answer>"}],
                "usage": {"input_tokens": 12, "output_tokens": 4},
            },
        },
        {
            "type": "result",
            "result": "<final_answer>7</final_answer>",
            "num_turns": 2,
            "usage": {"input_tokens": 12, "output_tokens": 4},
            "modelUsage": {"claude-sonnet-5": {"outputTokens": 4}},
        },
    ]
    result = ClaudeAdapter().parse_trace(trace, "", "", 99, 0)
    assert result.status == "ok"
    assert result.native_metrics["native_turns"] == 2
    assert result.native_metrics["primary_model"] == "claude-sonnet-5"
    assert result.native_metrics["observed_models"] == ["claude-sonnet-5"]
