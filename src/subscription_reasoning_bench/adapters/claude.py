from __future__ import annotations

import shutil
from collections import Counter
from typing import Any

from ..models import AdapterResult, RunConfig
from .base import Adapter, add_usage, cli_version


class ClaudeAdapter(Adapter):
    name = "claude"
    models = {"claude-opus-4-8", "claude-sonnet-5", "claude-fable-5"}
    efforts = {"high", "xhigh", "max"}

    def __init__(self, binary: str | None = None):
        self.binary = binary or shutil.which("claude") or "claude"

    def validate_config(self, config: RunConfig) -> None:
        if config.provider != self.name:
            raise ValueError(f"Claude adapter cannot run provider {config.provider}")
        if config.model not in self.models:
            raise ValueError(f"unsupported Claude model: {config.model}")
        if config.effort not in self.efforts:
            if config.effort == "ultra":
                raise ValueError("Claude has ultracode, not an ultra model effort; use high, xhigh, or max")
            raise ValueError(f"unsupported Claude effort: {config.effort}")
        if config.speed != "standard":
            raise ValueError("Claude subscription runs do not expose a Standard/Fast service-tier switch")

    def build_command(self, config: RunConfig) -> list[str]:
        return [
            self.binary,
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            config.model,
            "--effort",
            config.effort,
            "--safe-mode",
            "--no-chrome",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--tools",
            "",
            "--disallowed-tools",
            "*",
            "--no-session-persistence",
            "--system-prompt",
            "You are a text-only reasoning benchmark participant. Follow the user prompt exactly.",
        ]

    def parse_trace(
        self, trace: list[dict[str, Any]], stdout: str, stderr: str, latency_ms: int, exit_code: int
    ) -> AdapterResult:
        event_types: Counter[str] = Counter()
        content_types: Counter[str] = Counter()
        usage: dict[str, int] = {}
        response = ""
        native_turns = 0
        primary_model: str | None = None
        observed_models: set[str] = set()
        for event in trace:
            event_type = str(event.get("type", "unknown"))
            event_types[event_type] += 1
            model = event.get("model")
            if isinstance(model, str):
                observed_models.add(model)
            message = event.get("message")
            if isinstance(message, dict):
                message_model = message.get("model")
                if isinstance(message_model, str):
                    primary_model = message_model
                    observed_models.add(message_model)
                if isinstance(message.get("usage"), dict):
                    add_usage(usage, message["usage"])
                content = message.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        block_type = str(block.get("type", "unknown"))
                        content_types[block_type] += 1
                        text = block.get("text")
                        if block_type == "text" and isinstance(text, str):
                            response = text
            if event_type == "result":
                if isinstance(event.get("result"), str):
                    response = event["result"]
                if isinstance(event.get("num_turns"), int):
                    native_turns = event["num_turns"]
                if isinstance(event.get("usage"), dict):
                    usage = {}
                    add_usage(usage, event["usage"])
                model_usage = event.get("modelUsage") or event.get("model_usage")
                if isinstance(model_usage, dict):
                    observed_models.update(str(key) for key in model_usage)
        external_tool_calls = content_types.get("tool_use", 0)
        status = "ok" if exit_code == 0 and response else "error"
        error = None if status == "ok" else (stderr.strip() or "Claude returned no final message")
        metrics: dict[str, Any] = {
            **usage,
            "cli_version": cli_version(self.binary),
            "native_turns": native_turns,
            "reasoning_events": content_types.get("thinking", 0),
            "message_events": content_types.get("text", 0),
            "external_tool_calls": external_tool_calls,
            "subagent_calls": 0,
            "event_types": dict(event_types),
            "content_types": dict(content_types),
            "primary_model": primary_model,
            "observed_models": sorted(observed_models),
        }
        return AdapterResult(status, response, latency_ms, exit_code, metrics, trace, error)
