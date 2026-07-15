from subscription_reasoning_bench.adapters.claude import ClaudeAdapter
from subscription_reasoning_bench.adapters.codex import CodexAdapter
from subscription_reasoning_bench.models import AdapterResult, RunConfig


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
        {
            "type": "thread.started",
            "model": "gpt-5.6-sol",
            "thread_id": "11111111-1111-1111-1111-111111111111",
        },
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
    assert result.native_metrics["session_id"] == "11111111-1111-1111-1111-111111111111"


def test_codex_research_command_is_writable_and_persistent(tmp_path):
    config = RunConfig("codex", "gpt-5.6-sol", "high", "standard")
    command = CodexAdapter("codex").build_research_command(config, tmp_path.resolve())
    assert command[:7] == [
        "codex",
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
        "--cd",
        str(tmp_path.resolve()),
    ]
    assert "--ephemeral" not in command
    assert "resume" not in command
    assert "browser_use" in command
    assert "computer_use" in command
    assert 'web_search="disabled"' in command
    assert command[-1] == "-"


def test_codex_research_command_resumes_same_session_and_preserves_fast(tmp_path):
    session_id = "11111111-1111-1111-1111-111111111111"
    config = RunConfig("codex", "gpt-5.6-sol", "xhigh", "fast")
    command = CodexAdapter("codex").build_research_command(
        config, tmp_path.resolve(), session_id
    )
    assert command[command.index("exec") + 1] == "resume"
    assert command[-2:] == [session_id, "-"]
    assert 'service_tier="fast"' in command
    assert "--color" not in command


def test_research_turn_retains_requested_session_when_trace_is_incomplete(tmp_path, monkeypatch):
    session_id = "11111111-1111-1111-1111-111111111111"
    adapter = CodexAdapter("codex")

    def fake_run(command, config, prompt, cwd):
        assert command[-2:] == [session_id, "-"]
        assert prompt == "continue"
        assert cwd == tmp_path.resolve()
        return AdapterResult("timeout", "", 10, -1, {"session_id": None}, [], "timeout")

    monkeypatch.setattr(adapter, "_run_command", fake_run)
    result = adapter.run_research_turn(
        RunConfig("codex", "gpt-5.6-sol", "high"),
        "continue",
        tmp_path,
        session_id=session_id,
    )
    assert result.native_metrics["session_id"] == session_id
    assert result.native_metrics["requested_session_id"] == session_id


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
        {
            "type": "system",
            "subtype": "init",
            "model": "claude-sonnet-5",
            "session_id": "22222222-2222-2222-2222-222222222222",
        },
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
    assert result.native_metrics["session_id"] == "22222222-2222-2222-2222-222222222222"


def test_claude_research_command_enables_local_tools_and_persistence(tmp_path):
    config = RunConfig("claude", "claude-sonnet-5", "high")
    command = ClaudeAdapter("claude").build_research_command(config, tmp_path.resolve())
    tools = "Bash,Read,Edit,Write,Glob,Grep"
    assert command[command.index("--tools") + 1] == tools
    assert command[command.index("--allowed-tools") + 1] == tools
    assert command[command.index("--disallowed-tools") + 1] == "WebSearch,WebFetch"
    assert "--no-chrome" in command
    assert "--strict-mcp-config" in command
    assert "--no-session-persistence" not in command
    assert "--resume" not in command


def test_claude_research_command_resumes_same_session(tmp_path):
    session_id = "22222222-2222-2222-2222-222222222222"
    config = RunConfig("claude", "claude-opus-4-8", "max")
    command = ClaudeAdapter("claude").build_research_command(
        config, tmp_path.resolve(), session_id
    )
    assert command[command.index("--resume") + 1] == session_id
    assert command[command.index("--model") + 1] == "claude-opus-4-8"
    assert command[command.index("--effort") + 1] == "max"
