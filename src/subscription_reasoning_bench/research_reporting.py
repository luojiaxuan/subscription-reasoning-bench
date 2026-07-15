from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from .reporting import bootstrap_ci, percentile


COMPLETED_STATUSES = {"completed", "target_reached"}
ROUND_METRICS = {
    "total_native_turns": "native_turns",
    "total_tool_calls": "external_tool_calls",
    "total_subagent_calls": "subagent_calls",
}


def is_final_research_record(record: dict[str, Any]) -> bool:
    """Return whether a JSONL object is a finalized long-horizon research run."""
    return (
        record.get("record_type") == "research"
        and record.get("is_final") is True
        and isinstance(record.get("rounds"), list)
        and isinstance(record.get("trajectory_metrics"), dict)
        and "final_score" in record
        and "baseline_score" in record
    )


def research_config_label(record: dict[str, Any]) -> str:
    return "/".join(
        str(record.get(key, "unknown"))
        for key in ("provider", "requested_model", "effort", "speed", "protocol")
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _numbers(records: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for record in records:
        value = _number(record.get(key))
        if value is not None:
            values.append(value)
    return values


def _trajectory_numbers(records: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for record in records:
        value = _number(record.get("trajectory_metrics", {}).get(key))
        if value is not None:
            values.append(value)
    return values


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _round_metric(round_record: dict[str, Any], metric: str) -> float:
    native_metrics = round_record.get("native_metrics", {})
    if not isinstance(native_metrics, dict):
        return 0.0
    return _number(native_metrics.get(metric)) or 0.0


def _trajectory_total(record: dict[str, Any], metric: str) -> float:
    value = _number(record.get("trajectory_metrics", {}).get(metric))
    if value is not None:
        return value
    round_metric = ROUND_METRICS.get(metric, metric)
    return sum(
        _round_metric(round_record, round_metric) for round_record in record.get("rounds", [])
    )


def _curve(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_round: dict[int, list[float]] = defaultdict(list)
    for record in group:
        for round_record in record.get("rounds", []):
            round_index = round_record.get("round_index")
            score = _number(round_record.get("score"))
            if isinstance(round_index, int) and not isinstance(round_index, bool) and score is not None:
                by_round[round_index].append(score)
    return [
        {
            "round_index": round_index,
            "n": len(scores),
            "score_mean": statistics.fmean(scores),
            "score_ci95": bootstrap_ci(scores, seed=round_index),
        }
        for round_index, scores in sorted(by_round.items())
    ]


def summarize_research(records: list[dict[str, Any]]) -> dict[str, Any]:
    final_records = [record for record in records if is_final_research_record(record)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in final_records:
        grouped[research_config_label(record)].append(record)

    configs = []
    for label, group in sorted(grouped.items()):
        first = group[0]
        completed = [
            record for record in group if str(record.get("status", "")).lower() in COMPLETED_STATUSES
        ]
        baselines = _numbers(group, "baseline_score")
        final_scores = _numbers(group, "final_score")
        targets = _numbers(group, "target_score")
        normalized_improvements = _trajectory_numbers(group, "normalized_improvement")
        first_improvement_rounds = _trajectory_numbers(group, "first_improvement_round")
        best_improvement_rounds = _trajectory_numbers(group, "best_improvement_round")
        round_latencies = [
            sum(
                _number(round_record.get("latency_ms")) or 0.0
                for round_record in record.get("rounds", [])
            )
            for record in group
        ]
        native_turns = [_trajectory_total(record, "total_native_turns") for record in group]
        tool_calls = [_trajectory_total(record, "total_tool_calls") for record in group]
        subagent_calls = [_trajectory_total(record, "total_subagent_calls") for record in group]
        early_terminated = [
            bool(record.get("trajectory_metrics", {}).get("early_terminated")) for record in group
        ]
        target_reached = [
            bool(record.get("trajectory_metrics", {}).get("target_reached")) for record in group
        ]
        configs.append(
            {
                "label": label,
                "provider": str(first.get("provider", "unknown")),
                "requested_model": str(first.get("requested_model", "unknown")),
                "effort": str(first.get("effort", "unknown")),
                "speed": str(first.get("speed", "unknown")),
                "protocol": str(first.get("protocol", "unknown")),
                "runs": len(group),
                "completed": len(completed),
                "completion_rate": len(completed) / len(group),
                "baseline_score_mean": _mean(baselines),
                "final_score_mean": _mean(final_scores),
                "target_score_mean": _mean(targets),
                "absolute_improvement_mean": _mean(
                    [
                        final_score - baseline
                        for record in group
                        if (final_score := _number(record.get("final_score"))) is not None
                        and (baseline := _number(record.get("baseline_score"))) is not None
                    ]
                ),
                "normalized_improvement_mean": _mean(normalized_improvements),
                "normalized_improvement_ci95": bootstrap_ci(normalized_improvements),
                "auc_over_rounds_mean": _mean(_trajectory_numbers(group, "auc_over_rounds")),
                "first_improvement_round_mean": _mean(first_improvement_rounds),
                "best_improvement_round_mean": _mean(best_improvement_rounds),
                "late_gain_fraction_mean": _mean(_trajectory_numbers(group, "late_gain_fraction")),
                "valid_round_ratio_mean": _mean(_trajectory_numbers(group, "valid_round_ratio")),
                "rounds_mean": statistics.fmean(len(record.get("rounds", [])) for record in group),
                "latency_p50_ms": percentile(round_latencies, 0.5),
                "latency_p95_ms": percentile(round_latencies, 0.95),
                "total_native_turns": int(sum(native_turns)),
                "total_native_turns_mean": statistics.fmean(native_turns),
                "total_tool_calls": int(sum(tool_calls)),
                "total_tool_calls_mean": statistics.fmean(tool_calls),
                "total_subagent_calls": int(sum(subagent_calls)),
                "total_subagent_calls_mean": statistics.fmean(subagent_calls),
                "early_termination_rate": statistics.fmean(early_terminated),
                "target_reach_rate": statistics.fmean(target_reached),
                "curve": _curve(group),
            }
        )

    return {
        "schema_version": 1,
        "total_runs": len(final_records),
        "config_count": len(configs),
        "configs": configs,
    }
