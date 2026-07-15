from __future__ import annotations

import json
from pathlib import Path

import pytest

from subscription_reasoning_bench.models import AdapterResult, RunConfig
from subscription_reasoning_bench.research_runner import (
    load_research_matrix_config,
    run_research_task,
)
from subscription_reasoning_bench.research_tasks import load_research_task

from test_research_tasks import make_task


class IncrementAdapter:
    name = "codex"

    def __init__(self, fail_on_call: int | None = None):
        self.calls = 0
        self.fail_on_call = fail_on_call
        self.requested_sessions: list[str | None] = []

    def validate_config(self, config):
        assert config.provider == "codex"

    def run_research_turn(self, config, prompt, cwd: Path, session_id=None):
        self.calls += 1
        self.requested_sessions.append(session_id)
        if self.fail_on_call == self.calls:
            raise RuntimeError("simulated interruption")
        score_path = cwd / "score.txt"
        score = min(0.9, float(score_path.read_text(encoding="utf-8")) + 0.4)
        score_path.write_text(f"{score}\n", encoding="utf-8")
        current_session = session_id or "session-1"
        return AdapterResult(
            "ok",
            f"raised score to {score}",
            10,
            0,
            {
                "session_id": current_session,
                "native_turns": 2,
                "external_tool_calls": 1,
                "subagent_calls": 0,
                "observed_models": [config.model],
                "primary_model": config.model,
            },
            [{"type": "fake"}],
        )


class MissingSessionAdapter(IncrementAdapter):
    def run_research_turn(self, config, prompt, cwd: Path, session_id=None):
        self.calls += 1
        self.requested_sessions.append(session_id)
        return AdapterResult(
            "timeout",
            "",
            10,
            -1,
            {
                "session_id": None,
                "native_turns": 0,
                "external_tool_calls": 0,
                "subagent_calls": 0,
                "observed_models": [],
                "primary_model": None,
            },
            [],
            "timeout",
        )


def config():
    return RunConfig("codex", "gpt-5.6-sol", "high", "standard", "strict", 10)


def test_research_runner_uses_persistent_session_grades_and_skips_finalized(tmp_path):
    task = load_research_task(make_task(tmp_path))
    output = tmp_path / "runs" / "result.jsonl"
    adapter = IncrementAdapter()

    record, skipped = run_research_task(
        task,
        config(),
        output=output,
        workspace_root=tmp_path / "workspaces",
        adapter=adapter,
        keep_traces=True,
    )

    assert skipped is False
    assert adapter.requested_sessions == [None, "session-1"]
    assert record["record_type"] == "research"
    assert record["is_final"] is True
    assert record["status"] == "target_reached"
    assert record["final_score"] == 0.9
    assert len(record["rounds"]) == 2
    assert record["rounds"][0]["trace_path"].endswith("round-001.jsonl")
    assert record["trajectory_metrics"]["total_native_turns"] == 4
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["run_key"] == record["run_key"]

    repeated, skipped = run_research_task(
        task,
        config(),
        output=output,
        workspace_root=tmp_path / "workspaces",
        adapter=IncrementAdapter(),
    )
    assert skipped is True
    assert repeated["run_id"] == record["run_id"]


def test_research_runner_resumes_atomic_checkpoint_after_interruption(tmp_path):
    task = load_research_task(make_task(tmp_path))
    output = tmp_path / "runs" / "result.jsonl"
    workspace_root = tmp_path / "workspaces"

    with pytest.raises(RuntimeError, match="simulated interruption"):
        run_research_task(
            task,
            config(),
            output=output,
            workspace_root=workspace_root,
            adapter=IncrementAdapter(fail_on_call=2),
        )

    checkpoints = list((workspace_root / ".checkpoints").glob("*.json"))
    assert len(checkpoints) == 1
    checkpoint = json.loads(checkpoints[0].read_text(encoding="utf-8"))
    assert len(checkpoint["rounds"]) == 1
    assert checkpoint["session_id"] == "session-1"

    adapter = IncrementAdapter()
    record, skipped = run_research_task(
        task,
        config(),
        output=output,
        workspace_root=workspace_root,
        adapter=adapter,
    )

    assert skipped is False
    assert adapter.requested_sessions == ["session-1"]
    assert record["resumed_from_checkpoint"] is True
    assert len(record["rounds"]) == 2
    assert not checkpoints[0].exists()


def test_load_research_matrix_expands_configs(tmp_path):
    task_dir = make_task(tmp_path)
    config_path = tmp_path / "research.toml"
    config_path.write_text(
        f"""tasks = [{json.dumps(str(task_dir))}]
output = "runs/results.jsonl"
workspace_root = "runs/workspaces"
repeats = 2
seed = 17

[[matrix]]
provider = "codex"
models = ["gpt-5.6-sol"]
efforts = ["high", "ultra"]
speeds = ["standard", "fast"]
protocol = "strict"
""",
        encoding="utf-8",
    )

    tasks, output, workspaces, configs, repeats, seed = load_research_matrix_config(
        config_path
    )

    assert [task.id for task in tasks] == ["toy"]
    assert output == (tmp_path / "runs/results.jsonl").resolve()
    assert workspaces == (tmp_path / "runs/workspaces").resolve()
    assert len(configs) == 4
    assert repeats == 2
    assert seed == 17


def test_missing_session_before_min_rounds_is_failed_run(tmp_path):
    task = load_research_task(make_task(tmp_path))
    record, skipped = run_research_task(
        task,
        config(),
        output=tmp_path / "runs/result.jsonl",
        workspace_root=tmp_path / "workspaces",
        adapter=MissingSessionAdapter(),
    )

    assert skipped is False
    assert record["status"] == "failed"
    assert record["termination_reason"] == "session_id_missing"
    assert len(record["rounds"]) == 1
