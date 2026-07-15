from pathlib import Path

import pytest

from subscription_reasoning_bench.models import Task
from subscription_reasoning_bench.suites import load_suite, suite_hash, write_suite


def test_suite_round_trip(tmp_path: Path):
    path = tmp_path / "suite.jsonl"
    write_suite([Task("a", "What?", "A", category="logic")], path)
    tasks = load_suite(path)
    assert tasks[0].id == "a"
    assert tasks[0].category == "logic"
    assert len(suite_hash(path)) == 64


def test_duplicate_task_ids_fail(tmp_path: Path):
    path = tmp_path / "suite.jsonl"
    write_suite([Task("a", "one", "1"), Task("a", "two", "2")], path)
    with pytest.raises(ValueError, match="duplicate"):
        load_suite(path)
