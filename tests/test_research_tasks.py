from __future__ import annotations

import json
import sys

import pytest

from subscription_reasoning_bench.research_tasks import load_research_task, run_grader


def make_task(tmp_path):
    task_dir = tmp_path / "task"
    starter = task_dir / "starter"
    starter.mkdir(parents=True)
    (starter / "score.txt").write_text("0.1\n", encoding="utf-8")
    (task_dir / "objective.md").write_text("Improve score.txt.", encoding="utf-8")
    (task_dir / "grader.py").write_text(
        """import argparse, json
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--split', required=True)
p.add_argument('--round', type=int, required=True)
a = p.parse_args()
score = float((a.workspace / 'score.txt').read_text())
print(json.dumps({'score': score, 'valid': True, 'metrics': {'split': a.split}, 'feedback': f'round={a.round}'}))
""",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        f"""schema_version = 1
id = "toy"
title = "Toy research"
objective_file = "objective.md"
starter_dir = "starter"
grader_command = [{json.dumps(sys.executable)}, "grader.py", "--workspace", "{{workspace}}", "--split", "{{split}}", "--round", "{{round}}"]
max_rounds = 3
min_rounds = 2
round_timeout_seconds = 10
baseline_score = 0.1
target_score = 0.8
higher_is_better = true
""",
        encoding="utf-8",
    )
    return task_dir


def test_load_research_task_and_run_objective_grader(tmp_path):
    task = load_research_task(make_task(tmp_path))
    result = run_grader(task, task.starter_dir, "validation", 1)

    assert task.id == "toy"
    assert task.min_rounds == 2
    assert task.validation_baseline_score == task.baseline_score == 0.1
    assert len(task.digest) == 64
    assert result.score == 0.1
    assert result.metrics == {"split": "validation"}
    assert result.feedback == "round=1"


def test_research_task_rejects_unknown_grader_placeholder(tmp_path):
    task_dir = make_task(tmp_path)
    manifest = task_dir / "task.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("{round}", "{unknown}"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported grader placeholder"):
        load_research_task(task_dir)


def test_research_task_rejects_inverted_target(tmp_path):
    task_dir = make_task(tmp_path)
    manifest = task_dir / "task.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("target_score = 0.8", "target_score = 0.05"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="target_score must exceed"):
        load_research_task(task_dir)


def test_research_task_digest_ignores_python_cache(tmp_path):
    task_dir = make_task(tmp_path)
    original = load_research_task(task_dir).digest
    cache = task_dir / "starter" / "__pycache__"
    cache.mkdir()
    (cache / "solution.cpython-314.pyc").write_bytes(b"transient")

    assert load_research_task(task_dir).digest == original
