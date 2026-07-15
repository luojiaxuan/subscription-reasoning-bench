from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from .models import Task

BBEH_REVISION = "80d12ca916b7158f22293fcf3144f4d3d854d4be"
BBEH_MINI_SHA256 = "14e77b3d6be68faa008d268abf53b1f8d2420ffdd762504a304dafc3f8d43026"
BBEH_MINI_URL = (
    "https://raw.githubusercontent.com/google-deepmind/bbeh/"
    f"{BBEH_REVISION}/bbeh/mini/data.json"
)


def load_suite(path: Path) -> list[Task]:
    tasks: list[Task] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                task = Task.from_dict(json.loads(line))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid task at {path}:{line_number}: {exc}") from exc
            if task.id in seen:
                raise ValueError(f"duplicate task id at {path}:{line_number}: {task.id}")
            seen.add(task.id)
            tasks.append(task)
    if not tasks:
        raise ValueError(f"suite is empty: {path}")
    return tasks


def write_suite(tasks: Iterable[Task], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def suite_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_bbeh_mini(output: Path) -> int:
    with urllib.request.urlopen(BBEH_MINI_URL, timeout=60) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != BBEH_MINI_SHA256:
        raise RuntimeError(f"BBEH checksum mismatch: expected {BBEH_MINI_SHA256}, got {digest}")
    source = json.loads(payload)
    examples = source.get("examples")
    if not isinstance(examples, list) or len(examples) != 460:
        raise RuntimeError("unexpected BBEH mini schema or example count")
    tasks = []
    for index, example in enumerate(examples):
        tasks.append(
            Task(
                id=f"bbeh-mini-{index:03d}",
                prompt=str(example["input"]),
                reference=str(example["target"]),
                scorer="bbeh",
                category="bbeh",
                source="google-deepmind/bbeh",
                metadata={
                    "revision": BBEH_REVISION,
                    "license": "Apache-2.0",
                    "source_index": index,
                    "source_url": BBEH_MINI_URL,
                },
            )
        )
    return write_suite(tasks, output)


def generate_reasoning_gym(
    dataset_names: list[str], output: Path, size: int, seed: int, config: dict[str, Any] | None = None
) -> int:
    try:
        import reasoning_gym
    except ImportError as exc:
        raise RuntimeError("install with `pip install -e '.[reasoning-gym]'`") from exc
    common_config = dict(config or {})
    generator_version = str(getattr(reasoning_gym, "__version__", "unknown"))
    tasks: list[Task] = []
    for dataset_name in dataset_names:
        dataset = reasoning_gym.create_dataset(dataset_name, size=size, seed=seed, **common_config)
        for index, entry in enumerate(dataset):
            tasks.append(
                Task(
                    id=f"rg-{dataset_name}-{seed}-{index:04d}",
                    prompt=str(entry["question"]),
                    reference=str(entry["answer"]),
                    scorer="reasoning_gym",
                    category=str(getattr(dataset, "category", "reasoning_gym")),
                    source="open-thought/reasoning-gym",
                    metadata={
                        "reasoning_gym_dataset": dataset_name,
                        "reasoning_gym_entry": entry,
                        "generator_seed": seed,
                        "generator_config": common_config,
                        "generator_version": generator_version,
                        "license": "Apache-2.0",
                    },
                )
            )
    return write_suite(tasks, output)
