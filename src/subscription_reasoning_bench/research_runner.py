from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import tomllib
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

from .adapters.base import Adapter
from .models import RunConfig
from .research_metrics import reached_target, trajectory_metrics
from .research_tasks import GraderResult, ResearchTask, load_research_task, run_grader
from .runner import adapter_for


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-") or "run"


def research_run_key(task: ResearchTask, config: RunConfig, attempt: int) -> str:
    identity = {
        "task_id": task.id,
        "task_digest": task.digest,
        "attempt": attempt,
        "provider": config.provider,
        "model": config.model,
        "effort": config.effort,
        "speed": config.speed,
        "protocol": config.protocol,
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
    label = _slug(f"{task.id}-{config.provider}-{config.model}-{config.effort}-{config.speed}")
    return f"{label}-a{attempt}-{digest}"


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def completed_research_records(output: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not output.exists():
        return records
    with output.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(value, dict)
                and value.get("record_type") == "research"
                and value.get("is_final") is True
                and isinstance(value.get("run_key"), str)
            ):
                records[value["run_key"]] = value
    return records


def _config_dict(config: RunConfig) -> dict[str, Any]:
    return {
        "provider": config.provider,
        "model": config.model,
        "effort": config.effort,
        "speed": config.speed,
        "protocol": config.protocol,
        "timeout_seconds": config.timeout_seconds,
    }


def _new_state(
    task: ResearchTask,
    config: RunConfig,
    attempt: int,
    run_key: str,
    workspace: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "run_key": run_key,
        "task_id": task.id,
        "task_digest": task.digest,
        "attempt": attempt,
        "config": _config_dict(config),
        "workspace": str(workspace),
        "started_at": _now(),
        "session_id": None,
        "rounds": [],
        "termination_reason": None,
    }


def _load_or_create_state(
    task: ResearchTask,
    config: RunConfig,
    attempt: int,
    run_key: str,
    workspace: Path,
    checkpoint: Path,
) -> tuple[dict[str, Any], bool]:
    if checkpoint.exists():
        value = json.loads(checkpoint.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("run_key") != run_key:
            raise RuntimeError(f"invalid research checkpoint: {checkpoint}")
        if value.get("task_digest") != task.digest or value.get("config") != _config_dict(config):
            raise RuntimeError(f"checkpoint does not match task/config: {checkpoint}")
        if Path(str(value.get("workspace"))).resolve() != workspace.resolve():
            raise RuntimeError(f"checkpoint workspace mismatch: {checkpoint}")
        if not workspace.is_dir() or not isinstance(value.get("rounds"), list):
            raise RuntimeError(f"checkpoint workspace or rounds are missing: {checkpoint}")
        return value, True
    if workspace.exists():
        raise RuntimeError(
            f"workspace exists without a checkpoint: {workspace}; move or remove this staging run"
        )
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        task.starter_dir,
        workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store"),
    )
    value = _new_state(task, config, attempt, run_key, workspace)
    _atomic_json(checkpoint, value)
    return value, False


def build_research_prompt(
    task: ResearchTask,
    config: RunConfig,
    round_index: int,
    previous: dict[str, Any] | None,
) -> str:
    if config.protocol == "strict":
        orchestration = "Do not delegate to subagents; perform the research yourself."
    else:
        orchestration = (
            "You may use internal subagents when useful, but remain responsible for the final artifact."
        )
    shared = f"""You are participating in a controlled, text-only AI research benchmark.

This is research round {round_index} of at most {task.max_rounds}.

Rules:
- Work only inside the current workspace and modify the submitted artifact there.
- You may inspect local files and run local experiments. Do not use network access, browsers,
  external sources, or files outside this workspace.
- {orchestration}
- Do not ask the user questions. Use this round to make measurable progress.
- End with a concise account of hypotheses, experiments, evidence, and edits. The harness will
  grade the workspace after your response and may send another research round.
"""
    if previous is None:
        return f"{shared}\nResearch objective:\n{task.objective}\n"
    feedback = {
        "score": previous.get("score"),
        "valid": previous.get("valid"),
        "metrics": previous.get("metrics", {}),
        "pi_feedback": previous.get("feedback", ""),
    }
    return (
        f"{shared}\nThe previous validation result was:\n"
        f"{json.dumps(feedback, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
        "Continue from the current workspace and improve the held-out generalization result.\n"
    )


def _write_trace(
    output: Path, run_key: str, round_index: int, trace: list[dict[str, Any]]
) -> str:
    trace_dir = output.parent / f"{output.stem}-research-traces" / run_key
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"round-{round_index:03d}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for event in trace:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return str(path)


def _round_record(
    round_index: int,
    adapter_result: Any,
    grader_result: GraderResult,
    trace_path: str | None,
) -> dict[str, Any]:
    value = {
        "round_index": round_index,
        "status": adapter_result.status,
        "response": adapter_result.response,
        "score": grader_result.score,
        "valid": grader_result.valid,
        "metrics": grader_result.metrics,
        "feedback": grader_result.feedback,
        "latency_ms": adapter_result.latency_ms,
        "exit_code": adapter_result.exit_code,
        "native_metrics": adapter_result.native_metrics,
        "error": adapter_result.error or grader_result.error,
    }
    if trace_path is not None:
        value["trace_path"] = trace_path
    return value


def run_research_task(
    task: ResearchTask,
    config: RunConfig,
    *,
    output: Path,
    workspace_root: Path,
    attempt: int = 1,
    keep_traces: bool = False,
    adapter: Adapter | None = None,
) -> tuple[dict[str, Any], bool]:
    if attempt < 1:
        raise ValueError("attempt must be positive")
    selected_adapter = adapter or adapter_for(config.provider)
    selected_adapter.validate_config(config)
    run_key = research_run_key(task, config, attempt)
    completed = completed_research_records(output)
    if run_key in completed:
        return completed[run_key], True

    workspace = (workspace_root / run_key).resolve()
    checkpoint = (workspace_root / ".checkpoints" / f"{run_key}.json").resolve()
    state, resumed = _load_or_create_state(
        task, config, attempt, run_key, workspace, checkpoint
    )
    rounds: list[dict[str, Any]] = state["rounds"]
    session_id = state.get("session_id")
    turn_config = replace(config, timeout_seconds=task.round_timeout_seconds)
    for round_index in range(len(rounds) + 1, task.max_rounds + 1):
        previous = rounds[-1] if rounds else None
        prompt = build_research_prompt(task, config, round_index, previous)
        adapter_result = selected_adapter.run_research_turn(
            turn_config, prompt, workspace, session_id=session_id
        )
        observed_session = adapter_result.native_metrics.get("session_id")
        if isinstance(observed_session, str) and observed_session:
            session_id = observed_session
        grader_result = run_grader(task, workspace, "validation", round_index)
        trace_path = (
            _write_trace(output, run_key, round_index, adapter_result.trace)
            if keep_traces
            else None
        )
        rounds.append(_round_record(round_index, adapter_result, grader_result, trace_path))
        state["session_id"] = session_id
        state["rounds"] = rounds
        _atomic_json(checkpoint, state)

        validation_target = grader_result.valid and reached_target(
            grader_result.score, task.target_score, task.higher_is_better
        )
        if validation_target and round_index >= task.min_rounds:
            state["termination_reason"] = "validation_target_reached"
            _atomic_json(checkpoint, state)
            break
        if session_id is None and round_index < task.max_rounds:
            state["termination_reason"] = "session_id_missing"
            _atomic_json(checkpoint, state)
            break

    final_grader = run_grader(task, workspace, "test", len(rounds))
    metrics = trajectory_metrics(
        rounds,
        baseline=task.baseline_score,
        target=task.target_score,
        final_score=final_grader.score,
        higher_is_better=task.higher_is_better,
        max_rounds=task.max_rounds,
        validation_baseline=task.validation_baseline_score,
    )
    metrics["validation_target_reached"] = state.get("termination_reason") == (
        "validation_target_reached"
    )
    observed_models = sorted(
        {
            str(model)
            for item in rounds
            for model in item.get("native_metrics", {}).get("observed_models", [])
        }
    )
    primary_models = [
        item.get("native_metrics", {}).get("primary_model")
        for item in rounds
        if item.get("native_metrics", {}).get("primary_model")
    ]
    if not final_grader.valid or len(rounds) < task.min_rounds:
        status = "failed"
    elif metrics["target_reached"]:
        status = "target_reached"
    else:
        status = "completed"
    record = {
        "schema_version": 1,
        "record_type": "research",
        "is_final": True,
        "run_id": state["run_id"],
        "run_key": run_key,
        "task_id": task.id,
        "task_title": task.title,
        "task_digest": task.digest,
        "attempt": attempt,
        "provider": config.provider,
        "requested_model": config.model,
        "observed_primary_model": primary_models[-1] if primary_models else None,
        "observed_models": observed_models,
        "effort": config.effort,
        "speed": config.speed,
        "protocol": config.protocol,
        "started_at": state["started_at"],
        "completed_at": _now(),
        "status": status,
        "termination_reason": state.get("termination_reason") or "round_budget_exhausted",
        "workspace": str(workspace),
        "session_id": session_id,
        "baseline_score": task.baseline_score,
        "validation_baseline_score": task.validation_baseline_score,
        "target_score": task.target_score,
        "higher_is_better": task.higher_is_better,
        "final_score": final_grader.score,
        "final_valid": final_grader.valid,
        "final_metrics": final_grader.metrics,
        "rounds": rounds,
        "trajectory_metrics": metrics,
        "resumed_from_checkpoint": resumed,
    }
    _append_jsonl(output, record)
    checkpoint.unlink(missing_ok=True)
    return record, False


def run_research_matrix(
    tasks: list[ResearchTask],
    configs: list[RunConfig],
    *,
    output: Path,
    workspace_root: Path,
    repeats: int,
    seed: int,
    keep_traces: bool = False,
) -> tuple[int, int]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    rng = random.Random(seed)
    jobs: list[tuple[ResearchTask, RunConfig, int]] = []
    for attempt in range(1, repeats + 1):
        shuffled_tasks = list(tasks)
        rng.shuffle(shuffled_tasks)
        for task in shuffled_tasks:
            shuffled_configs = list(configs)
            rng.shuffle(shuffled_configs)
            jobs.extend((task, config, attempt) for config in shuffled_configs)
    executed = 0
    skipped = 0
    for task, config, attempt in jobs:
        _, was_skipped = run_research_task(
            task,
            config,
            output=output,
            workspace_root=workspace_root,
            attempt=attempt,
            keep_traces=keep_traces,
        )
        executed += not was_skipped
        skipped += was_skipped
    return executed, skipped


def load_research_matrix_config(
    path: Path,
) -> tuple[list[ResearchTask], Path, Path, list[RunConfig], int, int]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    base = path.parent.parent if path.parent.name == "configs" else path.parent
    task_paths = value.get("tasks", [])
    if not isinstance(task_paths, list) or not task_paths:
        raise ValueError(f"research matrix has no tasks: {path}")
    tasks = [load_research_task((base / str(task_path)).resolve()) for task_path in task_paths]
    output = (base / str(value["output"])).resolve()
    workspace_root = (base / str(value.get("workspace_root", "runs/research-workspaces"))).resolve()
    repeats = int(value.get("repeats", 1))
    seed = int(value.get("seed", 20260715))
    default_protocol = str(value.get("protocol", "strict"))
    configs: list[RunConfig] = []
    for group in value.get("matrix", []):
        provider = str(group["provider"])
        models = [str(item) for item in group.get("models", [])]
        efforts = [str(item) for item in group.get("efforts", [])]
        speeds = [str(item) for item in group.get("speeds", ["standard"])]
        protocol = str(group.get("protocol", default_protocol))
        for model, effort, speed in product(models, efforts, speeds):
            config = RunConfig(provider, model, effort, speed, protocol)  # type: ignore[arg-type]
            adapter_for(provider).validate_config(config)
            configs.append(config)
    if repeats < 1:
        raise ValueError("repeats must be positive")
    if not configs:
        raise ValueError(f"research matrix has no configurations: {path}")
    return tasks, output, workspace_root, configs, repeats, seed
