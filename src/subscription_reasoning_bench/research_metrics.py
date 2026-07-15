from __future__ import annotations

import math
from typing import Any


def directional_improvement(score: float, baseline: float, higher_is_better: bool) -> float:
    return score - baseline if higher_is_better else baseline - score


def normalized_improvement(
    score: float, baseline: float, target: float, higher_is_better: bool
) -> float:
    achieved = directional_improvement(score, baseline, higher_is_better)
    required = directional_improvement(target, baseline, higher_is_better)
    return achieved / required


def reached_target(score: float, target: float, higher_is_better: bool) -> bool:
    return score >= target if higher_is_better else score <= target


def trajectory_metrics(
    rounds: list[dict[str, Any]],
    *,
    baseline: float,
    target: float,
    final_score: float,
    higher_is_better: bool,
    max_rounds: int,
    validation_baseline: float | None = None,
) -> dict[str, Any]:
    process_baseline = baseline if validation_baseline is None else validation_baseline
    valid_rounds = [
        item
        for item in rounds
        if item.get("valid") is True
        and isinstance(item.get("score"), (int, float))
        and not isinstance(item.get("score"), bool)
        and math.isfinite(float(item["score"]))
    ]
    scores = [float(item["score"]) for item in valid_rounds]
    progress = [
        normalized_improvement(score, process_baseline, target, higher_is_better)
        for score in scores
    ]
    auc = 0.0
    if progress:
        points = [0.0, *progress]
        auc = sum((left + right) / 2 for left, right in zip(points, points[1:])) / len(
            progress
        )

    first_improvement_round: int | None = None
    best_improvement_round: int | None = None
    best_progress = 0.0
    positive_gains: list[tuple[int, float]] = []
    previous_best = 0.0
    for item, item_progress in zip(valid_rounds, progress):
        round_index = int(item["round_index"])
        if item_progress > 0 and first_improvement_round is None:
            first_improvement_round = round_index
        if item_progress > best_progress:
            best_progress = item_progress
            best_improvement_round = round_index
        gain = max(0.0, item_progress - previous_best)
        if gain:
            positive_gains.append((round_index, gain))
            previous_best = item_progress

    midpoint = max_rounds / 2
    total_gain = sum(gain for _, gain in positive_gains)
    late_gain = sum(gain for round_index, gain in positive_gains if round_index > midpoint)
    target_reached = reached_target(final_score, target, higher_is_better)
    native_turns = sum(int(item.get("native_metrics", {}).get("native_turns", 0)) for item in rounds)
    tool_calls = sum(
        int(item.get("native_metrics", {}).get("external_tool_calls", 0)) for item in rounds
    )
    subagent_calls = sum(
        int(item.get("native_metrics", {}).get("subagent_calls", 0)) for item in rounds
    )
    return {
        "normalized_improvement": normalized_improvement(
            final_score, baseline, target, higher_is_better
        ),
        "auc_over_rounds": auc,
        "first_improvement_round": first_improvement_round,
        "best_improvement_round": best_improvement_round,
        "late_gain_fraction": late_gain / total_gain if total_gain else 0.0,
        "valid_round_ratio": len(valid_rounds) / len(rounds) if rounds else 0.0,
        "total_native_turns": native_turns,
        "total_tool_calls": tool_calls,
        "total_subagent_calls": subagent_calls,
        "early_terminated": len(rounds) < max_rounds and not target_reached,
        "target_reached": target_reached,
    }
