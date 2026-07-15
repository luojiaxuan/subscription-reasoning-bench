from pathlib import Path

from subscription_reasoning_bench.cli import main


ROOT = Path(__file__).resolve().parent.parent


def test_research_validate_runs_both_grader_splits(capsys):
    status = main(["research", "validate", str(ROOT / "examples/research-toy")])
    output = capsys.readouterr().out

    assert status == 0
    assert '"task_id": "nonlinear-classifier-discovery"' in output
    assert '"starter_validation"' in output
    assert '"starter_test"' in output


def test_research_matrix_dry_run_is_quota_safe(capsys):
    status = main(
        ["research", "matrix", str(ROOT / "configs/research-matrix.toml"), "--dry-run"]
    )
    output = capsys.readouterr().out

    assert status == 0
    assert "configs=17" in output
    assert "planned_runs=17" in output
    assert "max_research_rounds=51" in output
    assert "claude/claude-fable-5/max" in output
