from subscription_reasoning_bench.reporting import summarize


def record(effort: str, score: float, latency: int, task_id: str = "a"):
    return {
        "task_id": task_id,
        "attempt": 1,
        "provider": "codex",
        "requested_model": "gpt-5.6-sol",
        "effort": effort,
        "speed": "standard",
        "protocol": "strict",
        "score": score,
        "latency_ms": latency,
        "protocol_violation": False,
        "native_metrics": {"native_turns": 1, "reasoning_events": 2},
    }


def test_summary_and_paired_delta():
    summary = summarize([record("high", 0, 100), record("xhigh", 1, 200)])
    assert summary["total_runs"] == 2
    assert len(summary["configs"]) == 2
    assert summary["paired"][0]["n"] == 1
    assert abs(summary["paired"][0]["accuracy_delta_right_minus_left"]) == 1.0
