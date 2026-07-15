from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from subscription_reasoning_bench.server import (
    capabilities,
    find_ui_dir,
    make_handler,
    short_records,
)

def test_ui_assets_exist():
    ui_dir = find_ui_dir()
    assert (ui_dir / "index.html").is_file()
    assert (ui_dir / "app.js").is_file()


def test_capability_matrix_does_not_claim_claude_ultra():
    matrix = capabilities()
    assert "ultra" in matrix["codex"]["efforts"]
    assert "ultra" not in matrix["claude"]["efforts"]


def test_short_records_excludes_research_and_research_checkpoints():
    short = {"task_id": "short-1"}
    assert short_records(
        [short, _research_record(), {"record_type": "research_checkpoint"}]
    ) == [short]


def test_server_exposes_separate_short_and_research_summaries(tmp_path):
    short = {
        "provider": "codex",
        "requested_model": "gpt-5.6-sol",
        "effort": "high",
        "speed": "standard",
        "protocol": "strict",
        "task_id": "short-1",
        "attempt": 0,
        "score": 1.0,
        "latency_ms": 100,
        "native_metrics": {"native_turns": 1},
    }
    results = tmp_path / "mixed.jsonl"
    results.write_text(
        "\n".join(json.dumps(record) for record in (short, _research_record())) + "\n",
        encoding="utf-8",
    )
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(tmp_path, find_ui_dir())
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        with urlopen(f"{base_url}/api/summary") as response:
            short_summary = json.load(response)
        with urlopen(f"{base_url}/api/research-summary") as response:
            research_summary = json.load(response)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert short_summary["total_runs"] == 1
    assert research_summary["total_runs"] == 1
    assert research_summary["configs"][0]["curve"][-1]["score_mean"] == 3.0


def _research_record():
    return {
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
            {"round_index": 1, "score": 1.5, "latency_ms": 1000, "native_metrics": {}},
            {"round_index": 2, "score": 3.0, "latency_ms": 2000, "native_metrics": {}},
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
