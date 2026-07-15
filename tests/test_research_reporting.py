from __future__ import annotations

from copy import deepcopy

import pytest

from subscription_reasoning_bench.research_reporting import (
    is_final_research_record,
    summarize_research,
)


def research_record(**overrides):
    record = {
        "record_type": "research",
        "is_final": True,
        "provider": "codex",
        "requested_model": "gpt-5.6-sol",
        "effort": "ultra",
        "speed": "standard",
        "protocol": "strict",
        "status": "completed",
        "baseline_score": 1.0,
        "final_score": 3.0,
        "target_score": 4.0,
        "rounds": [
            {
                "round_index": 1,
                "score": 1.5,
                "latency_ms": 1000,
                "native_metrics": {
                    "native_turns": 5,
                    "external_tool_calls": 2,
                    "subagent_calls": 1,
                },
            },
            {
                "round_index": 2,
                "score": 3.0,
                "latency_ms": 2000,
                "native_metrics": {
                    "native_turns": 7,
                    "external_tool_calls": 3,
                    "subagent_calls": 1,
                },
            },
        ],
        "trajectory_metrics": {
            "normalized_improvement": 0.5,
            "auc_over_rounds": 0.6,
            "first_improvement_round": 1,
            "best_improvement_round": 2,
            "late_gain_fraction": 0.4,
            "valid_round_ratio": 1.0,
            "total_native_turns": 12,
            "total_tool_calls": 5,
            "total_subagent_calls": 2,
            "early_terminated": False,
            "target_reached": False,
        },
    }
    record.update(overrides)
    return record


def test_is_final_research_record_requires_explicit_final_marker():
    assert is_final_research_record(research_record())
    assert not is_final_research_record(research_record(is_final=False))
    assert not is_final_research_record(research_record(record_type="research_checkpoint"))
    assert not is_final_research_record({"record_type": "short", "is_final": True})


def test_summarize_research_aggregates_trajectories_and_ignores_other_records():
    second = deepcopy(research_record())
    second.update({"status": "failed", "final_score": 4.0})
    second["rounds"][0]["score"] = 2.5
    second["rounds"][1]["score"] = 4.0
    second["trajectory_metrics"].update(
        {
            "normalized_improvement": 0.75,
            "auc_over_rounds": 0.8,
            "first_improvement_round": 2,
            "best_improvement_round": 2,
            "late_gain_fraction": 0.6,
            "valid_round_ratio": 0.5,
            "total_native_turns": 16,
            "total_tool_calls": 7,
            "total_subagent_calls": 4,
            "early_terminated": True,
            "target_reached": True,
        }
    )
    summary = summarize_research(
        [
            research_record(),
            second,
            research_record(is_final=False),
            {"record_type": "short", "score": 1.0},
        ]
    )

    assert summary["total_runs"] == 2
    assert summary["config_count"] == 1
    row = summary["configs"][0]
    assert row["label"] == "codex/gpt-5.6-sol/ultra/standard/strict"
    assert row["completed"] == 1
    assert row["completion_rate"] == 0.5
    assert row["final_score_mean"] == 3.5
    assert row["absolute_improvement_mean"] == 2.5
    assert row["normalized_improvement_mean"] == 0.625
    assert row["auc_over_rounds_mean"] == pytest.approx(0.7)
    assert row["first_improvement_round_mean"] == 1.5
    assert row["late_gain_fraction_mean"] == 0.5
    assert row["valid_round_ratio_mean"] == 0.75
    assert row["total_native_turns"] == 28
    assert row["total_tool_calls"] == 12
    assert row["total_subagent_calls"] == 6
    assert row["early_termination_rate"] == 0.5
    assert row["target_reach_rate"] == 0.5
    assert row["curve"] == [
        {"round_index": 1, "n": 2, "score_mean": 2.0, "score_ci95": [1.5, 2.5]},
        {"round_index": 2, "n": 2, "score_mean": 3.5, "score_ci95": [3.0, 4.0]},
    ]


def test_summarize_research_uses_round_native_metrics_as_fallback():
    record = research_record()
    for key in ("total_native_turns", "total_tool_calls", "total_subagent_calls"):
        del record["trajectory_metrics"][key]

    row = summarize_research([record])["configs"][0]

    assert row["total_native_turns"] == 12
    assert row["total_tool_calls"] == 5
    assert row["total_subagent_calls"] == 2
