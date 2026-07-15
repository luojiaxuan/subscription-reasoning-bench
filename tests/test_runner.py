from pathlib import Path

from subscription_reasoning_bench.runner import build_prompt, load_matrix_config, make_jobs
from subscription_reasoning_bench.models import RunConfig, Task


def test_prompt_protocols_are_distinct():
    task = Task("a", "Puzzle", "answer")
    strict = build_prompt(task, "strict")
    orchestrated = build_prompt(task, "orchestrated")
    assert "Do not call any tool" in strict
    assert "internal subagents" in orchestrated
    assert "<final_answer>" in strict


def test_jobs_keep_every_configuration_paired():
    tasks = [Task("a", "A", "1"), Task("b", "B", "2")]
    configs = [
        RunConfig("codex", "gpt-5.6-sol", "high"),
        RunConfig("codex", "gpt-5.6-sol", "xhigh"),
    ]
    jobs = make_jobs(tasks, configs, repeats=3, seed=7)
    assert len(jobs) == 12
    keys = {(task.id, attempt, config.effort) for task, config, attempt in jobs}
    assert len(keys) == 12


def test_full_matrix_expands_requested_capabilities():
    path = Path(__file__).parents[1] / "configs" / "subscription-matrix.toml"
    _, _, configs, repeats, _ = load_matrix_config(path)
    assert repeats == 3
    assert len(configs) == 17
    assert sum(config.provider == "codex" for config in configs) == 8
    assert sum(config.provider == "claude" for config in configs) == 9
