import pytest

from subscription_reasoning_bench.research_metrics import trajectory_metrics


def test_trajectory_metrics_capture_late_progress_and_process_cost():
    rounds = [
        {
            "round_index": 1,
            "score": 0.2,
            "valid": True,
            "native_metrics": {
                "native_turns": 2,
                "external_tool_calls": 3,
                "subagent_calls": 0,
            },
        },
        {
            "round_index": 2,
            "score": 0.5,
            "valid": True,
            "native_metrics": {
                "native_turns": 4,
                "external_tool_calls": 2,
                "subagent_calls": 1,
            },
        },
        {
            "round_index": 3,
            "score": 0.8,
            "valid": True,
            "native_metrics": {
                "native_turns": 5,
                "external_tool_calls": 1,
                "subagent_calls": 0,
            },
        },
    ]
    metrics = trajectory_metrics(
        rounds,
        baseline=0.0,
        target=1.0,
        final_score=0.8,
        higher_is_better=True,
        max_rounds=4,
    )

    assert metrics["normalized_improvement"] == 0.8
    assert metrics["auc_over_rounds"] == 0.3666666666666667
    assert metrics["first_improvement_round"] == 1
    assert metrics["best_improvement_round"] == 3
    assert metrics["late_gain_fraction"] == pytest.approx(0.375)
    assert metrics["valid_round_ratio"] == 1.0
    assert metrics["total_native_turns"] == 11
    assert metrics["total_tool_calls"] == 6
    assert metrics["total_subagent_calls"] == 1
    assert metrics["early_terminated"] is True
    assert metrics["target_reached"] is False


def test_lower_score_can_be_better():
    metrics = trajectory_metrics(
        [{"round_index": 1, "score": 4.0, "valid": True, "native_metrics": {}}],
        baseline=10.0,
        target=2.0,
        final_score=2.0,
        higher_is_better=False,
        max_rounds=1,
    )

    assert metrics["normalized_improvement"] == 1.0
    assert metrics["target_reached"] is True
    assert metrics["early_terminated"] is False
