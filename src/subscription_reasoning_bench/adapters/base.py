from __future__ import annotations

import json
import subprocess
import time
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..models import AdapterResult, RunConfig


class Adapter(ABC):
    name: str

    @abstractmethod
    def validate_config(self, config: RunConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_command(self, config: RunConfig) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def parse_trace(
        self, trace: list[dict[str, Any]], stdout: str, stderr: str, latency_ms: int, exit_code: int
    ) -> AdapterResult:
        raise NotImplementedError

    def run(self, config: RunConfig, prompt: str, cwd: Path) -> AdapterResult:
        self.validate_config(config)
        command = self.build_command(config)
        started = time.monotonic()
        try:
            process = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=cwd,
                timeout=config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            latency_ms = round((time.monotonic() - started) * 1000)
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            trace = parse_json_lines(stdout)
            result = self.parse_trace(trace, stdout, stderr, latency_ms, -1)
            result.status = "timeout"
            result.error = f"timed out after {config.timeout_seconds} seconds"
            return result
        latency_ms = round((time.monotonic() - started) * 1000)
        trace = parse_json_lines(process.stdout)
        return self.parse_trace(trace, process.stdout, process.stderr, latency_ms, process.returncode)


def parse_json_lines(output: str) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            trace.append(value)
    return trace


def add_usage(total: dict[str, int], usage: dict[str, Any]) -> None:
    aliases = {
        "input_tokens": ("input_tokens", "inputTokens"),
        "output_tokens": ("output_tokens", "outputTokens"),
        "cached_input_tokens": (
            "cached_input_tokens",
            "cache_read_input_tokens",
            "cacheReadInputTokens",
        ),
        "cache_creation_input_tokens": (
            "cache_creation_input_tokens",
            "cacheCreationInputTokens",
        ),
        "reasoning_tokens": ("reasoning_tokens", "reasoningTokens"),
    }
    for canonical, keys in aliases.items():
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int):
                total[canonical] = total.get(canonical, 0) + value
                break


@lru_cache(maxsize=None)
def cli_version(binary: str) -> str:
    try:
        process = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return (process.stdout.strip() or process.stderr.strip() or "unknown").splitlines()[0]
