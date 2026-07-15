from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from ..models import AdapterResult, RunConfig
from .base import Adapter, add_usage, cli_version


def resolve_codex_binary() -> str:
    app_binary = Path("/Applications/Codex.app/Contents/Resources/codex")
    if app_binary.is_file():
        return str(app_binary)
    return shutil.which("codex") or "codex"


class CodexAdapter(Adapter):
    name = "codex"
    models = {"gpt-5.6-sol"}
    efforts = {"high", "xhigh", "max", "ultra"}
    speeds = {"standard", "fast"}

    def __init__(self, binary: str | None = None):
        self.binary = binary or resolve_codex_binary()

    def validate_config(self, config: RunConfig) -> None:
        if config.provider != self.name:
            raise ValueError(f"Codex adapter cannot run provider {config.provider}")
        if config.model not in self.models:
            raise ValueError(f"unsupported Codex model: {config.model}")
        if config.effort not in self.efforts:
            raise ValueError(f"unsupported Codex effort: {config.effort}")
        if config.speed not in self.speeds:
            raise ValueError(f"unsupported Codex speed: {config.speed}")

    def build_command(self, config: RunConfig) -> list[str]:
        command = [
            self.binary,
            "exec",
            "--model",
            config.model,
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--json",
            "--color",
            "never",
            "--disable",
            "browser_use",
            "--disable",
            "computer_use",
            "-c",
            'web_search="disabled"',
            "-c",
            f'model_reasoning_effort="{config.effort}"',
        ]
        if config.speed == "fast":
            command.extend(["--enable", "fast_mode", "-c", 'service_tier="fast"'])
        else:
            command.extend(["--disable", "fast_mode"])
        command.append("-")
        return command

    def build_research_command(
        self, config: RunConfig, cwd: Path, session_id: str | None = None
    ) -> list[str]:
        command = [
            self.binary,
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "never",
            "--cd",
            str(cwd),
            "exec",
        ]
        if session_id is not None:
            command.append("resume")
        command.extend(
            [
                "--model",
                config.model,
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--json",
                "--disable",
                "browser_use",
                "--disable",
                "computer_use",
                "-c",
                'web_search="disabled"',
                "-c",
                f'model_reasoning_effort="{config.effort}"',
            ]
        )
        if config.speed == "fast":
            command.extend(["--enable", "fast_mode", "-c", 'service_tier="fast"'])
        else:
            command.extend(["--disable", "fast_mode"])
        if session_id is None:
            command.extend(["--color", "never"])
        else:
            command.append(session_id)
        command.append("-")
        return command

    def parse_trace(
        self, trace: list[dict[str, Any]], stdout: str, stderr: str, latency_ms: int, exit_code: int
    ) -> AdapterResult:
        event_types: Counter[str] = Counter()
        item_types: Counter[str] = Counter()
        usage: dict[str, int] = {}
        messages: list[str] = []
        observed_models: set[str] = set()
        observed_session_ids: set[str] = set()
        session_id: str | None = None
        external_tool_calls = 0
        subagent_calls = 0
        for event in trace:
            event_type = str(event.get("type", "unknown"))
            event_types[event_type] += 1
            if isinstance(event.get("usage"), dict):
                add_usage(usage, event["usage"])
            model = event.get("model")
            if isinstance(model, str):
                observed_models.add(model)
            event_session_id = (
                event.get("thread_id") or event.get("threadId") or event.get("session_id")
            )
            if isinstance(event_session_id, str):
                session_id = session_id or event_session_id
                observed_session_ids.add(event_session_id)
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "unknown"))
            item_types[item_type] += 1
            if item_type in {"agent_message", "assistant_message", "message"}:
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    messages.append(text)
            if item_type in {"command_execution", "mcp_tool_call", "web_search", "image_generation"}:
                external_tool_calls += 1
            serialized = json.dumps(item, sort_keys=True).lower()
            if "spawn_agent" in serialized or "subagent" in item_type or "collaboration" in item_type:
                subagent_calls += 1
            item_model = item.get("model")
            if isinstance(item_model, str):
                observed_models.add(item_model)
        response = messages[-1] if messages else ""
        status = "ok" if exit_code == 0 and response else "error"
        error = None if status == "ok" else (stderr.strip() or "Codex returned no final message")
        metrics: dict[str, Any] = {
            **usage,
            "cli_version": cli_version(self.binary),
            "native_turns": event_types.get("turn.started", 0),
            "reasoning_events": item_types.get("reasoning", 0),
            "message_events": sum(item_types[key] for key in ("agent_message", "assistant_message", "message")),
            "external_tool_calls": external_tool_calls,
            "subagent_calls": subagent_calls,
            "event_types": dict(event_types),
            "item_types": dict(item_types),
            "primary_model": None,
            "observed_models": sorted(observed_models),
            "session_id": session_id,
            "observed_session_ids": sorted(observed_session_ids),
        }
        return AdapterResult(status, response, latency_ms, exit_code, metrics, trace, error)
