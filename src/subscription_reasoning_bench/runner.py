from __future__ import annotations

import json
import os
import random
import tempfile
import tomllib
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Iterable

from .adapters import ClaudeAdapter, CodexAdapter
from .models import RunConfig, RunRecord, Task
from .scoring import score_response
from .suites import load_suite, suite_hash


def adapter_for(provider: str):
    if provider == "codex":
        return CodexAdapter()
    if provider == "claude":
        return ClaudeAdapter()
    raise ValueError(f"unknown provider: {provider}")


def build_prompt(task: Task, protocol: str) -> str:
    if protocol == "strict":
        orchestration = "Do not call any tool or delegate to another agent."
    else:
        orchestration = (
            "You may delegate text-only reasoning to internal subagents if the runtime supports it, "
            "but do not use files, shell commands, browsers, search, code execution, or external sources."
        )
    return f"""You are participating in a controlled text-only reasoning benchmark.

Rules:
- Use only the text in this prompt and your internal reasoning.
- {orchestration}
- Do not ask the user questions.
- End with exactly one line in this form: <final_answer>YOUR ANSWER</final_answer>

Question:
{task.prompt}
"""


def run_one(
    task: Task,
    config: RunConfig,
    attempt: int,
    current_suite_hash: str,
    trace_dir: Path | None = None,
) -> RunRecord:
    adapter = adapter_for(config.provider)
    started_at = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix="subscription-reasoning-bench-") as temp_dir:
        result = adapter.run(config, build_prompt(task, config.protocol), Path(temp_dir))
    answer = ""
    score: float | None = None
    correct: bool | None = None
    if result.status == "ok":
        try:
            answer, score = score_response(task, result.response)
            correct = score >= 1.0
        except Exception as exc:
            result.status = "scoring_error"
            result.error = str(exc)
    external_calls = int(result.native_metrics.get("external_tool_calls", 0))
    subagent_calls = int(result.native_metrics.get("subagent_calls", 0))
    protocol_violation = external_calls > 0 or (config.protocol == "strict" and subagent_calls > 0)
    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_path = trace_dir / f"{run_id}.jsonl"
        with trace_path.open("w", encoding="utf-8") as handle:
            for event in result.trace:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return RunRecord(
        schema_version=1,
        run_id=run_id,
        task_id=task.id,
        task_category=task.category,
        task_source=task.source,
        suite_hash=current_suite_hash,
        attempt=attempt,
        provider=config.provider,
        requested_model=config.model,
        observed_primary_model=result.native_metrics.get("primary_model"),
        observed_models=list(result.native_metrics.get("observed_models", [])),
        effort=config.effort,
        speed=config.speed,
        protocol=config.protocol,
        started_at=started_at,
        status=result.status,
        response=result.response,
        extracted_answer=answer,
        score=score,
        correct=correct,
        latency_ms=result.latency_ms,
        protocol_violation=protocol_violation,
        exit_code=result.exit_code,
        native_metrics=result.native_metrics,
        error=result.error,
    )


def append_record(path: Path, record: RunRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def record_key(value: dict[str, Any]) -> tuple[Any, ...]:
    return (
        value.get("task_id"),
        value.get("attempt"),
        value.get("provider"),
        value.get("requested_model"),
        value.get("effort"),
        value.get("speed"),
        value.get("protocol"),
    )


def completed_keys(output: Path) -> set[tuple[Any, ...]]:
    keys: set[tuple[Any, ...]] = set()
    if not output.exists():
        return keys
    with output.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                keys.add(record_key(json.loads(line)))
            except json.JSONDecodeError:
                continue
    return keys


def make_jobs(
    tasks: list[Task], configs: list[RunConfig], repeats: int, seed: int
) -> list[tuple[Task, RunConfig, int]]:
    rng = random.Random(seed)
    jobs: list[tuple[Task, RunConfig, int]] = []
    for attempt in range(1, repeats + 1):
        shuffled_tasks = list(tasks)
        rng.shuffle(shuffled_tasks)
        for task in shuffled_tasks:
            shuffled_configs = list(configs)
            rng.shuffle(shuffled_configs)
            jobs.extend((task, config, attempt) for config in shuffled_configs)
    return jobs


def run_matrix(
    suite: Path,
    output: Path,
    configs: list[RunConfig],
    repeats: int,
    seed: int,
    limit: int | None = None,
    keep_traces: bool = False,
) -> tuple[int, int]:
    tasks = load_suite(suite)
    if limit is not None:
        tasks = tasks[:limit]
    digest = suite_hash(suite)
    done = completed_keys(output)
    executed = 0
    skipped = 0
    trace_dir = output.parent / f"{output.stem}-traces" if keep_traces else None
    for task, config, attempt in make_jobs(tasks, configs, repeats, seed):
        key = record_key(
            {
                "task_id": task.id,
                "attempt": attempt,
                "provider": config.provider,
                "requested_model": config.model,
                "effort": config.effort,
                "speed": config.speed,
                "protocol": config.protocol,
            }
        )
        if key in done:
            skipped += 1
            continue
        record = run_one(task, config, attempt, digest, trace_dir)
        append_record(output, record)
        executed += 1
    return executed, skipped


def load_matrix_config(path: Path) -> tuple[Path, Path, list[RunConfig], int, int]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    base = path.parent.parent if path.parent.name == "configs" else path.parent
    suite = (base / str(value["suite"])).resolve()
    output = (base / str(value["output"])).resolve()
    repeats = int(value.get("repeats", 3))
    seed = int(value.get("seed", 20260715))
    default_timeout = int(value.get("timeout_seconds", 900))
    default_protocol = str(value.get("protocol", "strict"))
    configs: list[RunConfig] = []
    for group in value.get("matrix", []):
        provider = str(group["provider"])
        models = [str(item) for item in group.get("models", [])]
        efforts = [str(item) for item in group.get("efforts", [])]
        speeds = [str(item) for item in group.get("speeds", ["standard"])]
        protocol = str(group.get("protocol", default_protocol))
        timeout = int(group.get("timeout_seconds", default_timeout))
        for model, effort, speed in product(models, efforts, speeds):
            config = RunConfig(provider, model, effort, speed, protocol, timeout)  # type: ignore[arg-type]
            adapter_for(provider).validate_config(config)
            configs.append(config)
    if not configs:
        raise ValueError(f"matrix has no configurations: {path}")
    return suite, output, configs, repeats, seed


def with_timeout(configs: Iterable[RunConfig], timeout_seconds: int) -> list[RunConfig]:
    return [replace(config, timeout_seconds=timeout_seconds) for config in configs]
