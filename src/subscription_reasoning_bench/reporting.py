from __future__ import annotations

import json
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def config_label(record: dict[str, Any]) -> str:
    parts = [record["provider"], record["requested_model"], record["effort"]]
    if record["provider"] == "codex":
        parts.append(record["speed"])
    if record.get("protocol") != "strict":
        parts.append(str(record.get("protocol")))
    return "/".join(parts)


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return ordered[index]


def bootstrap_ci(values: list[float], seed: int = 0, samples: int = 2000) -> list[float] | None:
    if not values:
        return None
    if len(values) == 1:
        return [values[0], values[0]]
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        means.append(statistics.fmean(rng.choice(values) for _ in values))
    return [float(percentile(means, 0.025)), float(percentile(means, 0.975))]


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[config_label(record)].append(record)
    configs = []
    for label, group in sorted(grouped.items()):
        scores = [float(record.get("score") or 0.0) for record in group]
        valid_scores = [float(record["score"]) for record in group if record.get("score") is not None]
        latencies = [float(record["latency_ms"]) for record in group]
        turns = [float(record.get("native_metrics", {}).get("native_turns", 0)) for record in group]
        configs.append(
            {
                "label": label,
                "runs": len(group),
                "completed": len(valid_scores),
                "completion_rate": len(valid_scores) / len(group),
                "end_to_end_accuracy": statistics.fmean(scores),
                "accuracy_ci95": bootstrap_ci(scores),
                "valid_accuracy": statistics.fmean(valid_scores) if valid_scores else None,
                "latency_p50_ms": percentile(latencies, 0.5),
                "latency_p95_ms": percentile(latencies, 0.95),
                "native_turns_mean": statistics.fmean(turns),
                "reasoning_events_mean": statistics.fmean(
                    float(record.get("native_metrics", {}).get("reasoning_events", 0)) for record in group
                ),
                "external_tool_calls": sum(
                    int(record.get("native_metrics", {}).get("external_tool_calls", 0)) for record in group
                ),
                "subagent_calls": sum(
                    int(record.get("native_metrics", {}).get("subagent_calls", 0)) for record in group
                ),
                "protocol_violations": sum(bool(record.get("protocol_violation")) for record in group),
            }
        )
    return {"schema_version": 1, "total_runs": len(records), "configs": configs, "paired": paired_deltas(records)}


def paired_deltas(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_config: dict[str, dict[tuple[str, int], float]] = defaultdict(dict)
    for record in records:
        key = (str(record["task_id"]), int(record["attempt"]))
        by_config[config_label(record)][key] = float(record.get("score") or 0.0)
    labels = sorted(by_config)
    pairs = []
    for index, left in enumerate(labels):
        for right in labels[index + 1 :]:
            common = sorted(set(by_config[left]) & set(by_config[right]))
            if not common:
                continue
            deltas = [by_config[right][key] - by_config[left][key] for key in common]
            pairs.append(
                {
                    "left": left,
                    "right": right,
                    "n": len(common),
                    "accuracy_delta_right_minus_left": statistics.fmean(deltas),
                    "delta_ci95": bootstrap_ci(deltas, seed=index + len(pairs)),
                }
            )
    return pairs


def print_summary(summary: dict[str, Any]) -> None:
    header = f"{'configuration':64} {'n':>5} {'acc':>7} {'p50(s)':>8} {'turns':>7} {'viol':>5}"
    print(header)
    print("-" * len(header))
    for row in summary["configs"]:
        print(
            f"{row['label'][:64]:64} {row['runs']:5d} {row['end_to_end_accuracy']:7.3f} "
            f"{row['latency_p50_ms'] / 1000:8.2f} {row['native_turns_mean']:7.2f} "
            f"{row['protocol_violations']:5d}"
        )
