from __future__ import annotations

import hashlib
import json
import math
import string
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


Split = Literal["validation", "test"]
ALLOWED_GRADER_FIELDS = {"task_root", "workspace", "split", "round"}


@dataclass(frozen=True)
class ResearchTask:
    schema_version: int
    id: str
    title: str
    root: Path
    objective_file: Path
    starter_dir: Path
    grader_command: tuple[str, ...]
    max_rounds: int
    min_rounds: int
    round_timeout_seconds: int
    baseline_score: float
    target_score: float
    higher_is_better: bool
    digest: str

    @property
    def objective(self) -> str:
        return self.objective_file.read_text(encoding="utf-8").strip()

    def public_manifest(self) -> dict[str, Any]:
        value = asdict(self)
        value["root"] = str(self.root)
        value["objective_file"] = str(self.objective_file)
        value["starter_dir"] = str(self.starter_dir)
        value["grader_command"] = list(self.grader_command)
        return value


@dataclass(frozen=True)
class GraderResult:
    score: float
    valid: bool
    metrics: dict[str, Any]
    feedback: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _inside(root: Path, path: Path, label: str) -> Path:
    resolved = path.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"{label} escapes task root: {path}")
    return resolved


def _manifest_digest(root: Path, manifest: dict[str, Any]) -> str:
    hasher = hashlib.sha256()
    hasher.update(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hasher.update(path.relative_to(root).as_posix().encode())
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _validate_grader_command(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise ValueError("grader_command must be a non-empty array of strings")
    formatter = string.Formatter()
    for argument in value:
        for _, field, format_spec, conversion in formatter.parse(argument):
            if field is None:
                continue
            if field not in ALLOWED_GRADER_FIELDS or format_spec or conversion:
                raise ValueError(f"unsupported grader placeholder: {field}")
    return tuple(value)


def load_research_task(path: Path) -> ResearchTask:
    manifest_path = path / "task.toml" if path.is_dir() else path
    manifest_path = manifest_path.resolve(strict=True)
    root = manifest_path.parent
    with manifest_path.open("rb") as handle:
        value = tomllib.load(handle)
    if int(value.get("schema_version", 0)) != 1:
        raise ValueError("research task schema_version must be 1")
    task_id = str(value.get("id", "")).strip()
    title = str(value.get("title", "")).strip()
    if not task_id or not title:
        raise ValueError("research task id and title must be non-empty")
    objective_file = _inside(root, root / str(value["objective_file"]), "objective_file")
    starter_dir = _inside(root, root / str(value["starter_dir"]), "starter_dir")
    if not objective_file.is_file():
        raise ValueError("objective_file must be a file")
    if not starter_dir.is_dir():
        raise ValueError("starter_dir must be a directory")
    grader_command = _validate_grader_command(value.get("grader_command"))
    max_rounds = int(value.get("max_rounds", 0))
    min_rounds = int(value.get("min_rounds", 1))
    timeout = int(value.get("round_timeout_seconds", 0))
    if max_rounds < 1 or not 1 <= min_rounds <= max_rounds:
        raise ValueError("require 1 <= min_rounds <= max_rounds")
    if timeout < 1:
        raise ValueError("round_timeout_seconds must be positive")
    baseline = float(value["baseline_score"])
    target = float(value["target_score"])
    if not math.isfinite(baseline) or not math.isfinite(target) or baseline == target:
        raise ValueError("baseline_score and target_score must be finite and different")
    higher_is_better = value.get("higher_is_better")
    if not isinstance(higher_is_better, bool):
        raise ValueError("higher_is_better must be a boolean")
    if higher_is_better and target <= baseline:
        raise ValueError("target_score must exceed baseline_score when higher_is_better=true")
    if not higher_is_better and target >= baseline:
        raise ValueError("target_score must be below baseline_score when higher_is_better=false")
    return ResearchTask(
        schema_version=1,
        id=task_id,
        title=title,
        root=root,
        objective_file=objective_file,
        starter_dir=starter_dir,
        grader_command=grader_command,
        max_rounds=max_rounds,
        min_rounds=min_rounds,
        round_timeout_seconds=timeout,
        baseline_score=baseline,
        target_score=target,
        higher_is_better=higher_is_better,
        digest=_manifest_digest(root, value),
    )


def grader_argv(
    task: ResearchTask, workspace: Path, split: Split, round_index: int
) -> list[str]:
    if split not in {"validation", "test"}:
        raise ValueError(f"unsupported grader split: {split}")
    values = {
        "task_root": str(task.root),
        "workspace": str(workspace.resolve(strict=True)),
        "split": split,
        "round": str(round_index),
    }
    return [argument.format_map(values) for argument in task.grader_command]


def run_grader(
    task: ResearchTask, workspace: Path, split: Split, round_index: int
) -> GraderResult:
    try:
        process = subprocess.run(
            grader_argv(task, workspace, split, round_index),
            cwd=task.root,
            capture_output=True,
            text=True,
            timeout=task.round_timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"grader infrastructure failure: {exc}") from exc
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"grader exited with {process.returncode}: {detail}")
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"grader did not return one JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("grader output must be a JSON object")
    score = value.get("score")
    valid = value.get("valid")
    metrics = value.get("metrics", {})
    feedback = value.get("feedback", "")
    error = value.get("error")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        raise RuntimeError("grader score must be a finite number")
    if not isinstance(valid, bool) or not isinstance(metrics, dict) or not isinstance(feedback, str):
        raise RuntimeError("grader valid/metrics/feedback fields have invalid types")
    if error is not None and not isinstance(error, str):
        raise RuntimeError("grader error must be a string or null")
    return GraderResult(float(score), valid, metrics, feedback, error)
