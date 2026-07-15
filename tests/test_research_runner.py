from __future__ import annotations

import json
from pathlib import Path

import pytest

from subscription_reasoning_bench.models import AdapterResult, RunConfig
from subscription_reasoning_bench.research_runner import run_research_task
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
