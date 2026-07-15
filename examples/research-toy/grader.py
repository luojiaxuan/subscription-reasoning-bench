from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path
from types import ModuleType


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--round", type=int, required=True)
    return parser.parse_args()


def load_solution(workspace: Path) -> ModuleType:
    path = (workspace / "solution.py").resolve()
    if workspace.resolve() not in path.parents:
        raise ValueError("solution path escaped the workspace")
    spec = importlib.util.spec_from_file_location("candidate_solution", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load solution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def target(features: list[float]) -> int:
    x0, x1, x2, x3 = features
    margin = 1.4 * x0 * x1 + 0.8 * x2 - 0.45 * x3 + 0.2 * x0
    return int(margin > 0.0)


def make_examples(split: str) -> list[tuple[list[float], int]]:
    seed = 20260715 if split == "validation" else 20260716
    rng = random.Random(seed)
    examples = []
    for _ in range(400):
        features = [rng.uniform(-1.0, 1.0) for _ in range(4)]
        examples.append((features, target(features)))
    return examples


def pi_feedback(score: float, round_index: int, split: str) -> str:
    if split == "test":
        return ""
    if score < 0.80:
        return (
            "The baseline has not improved. Inspect pairwise feature interactions instead of "
            "ranking only marginal correlations."
        )
    if score < 0.90:
        return (
            "The strongest missed structure is a nonlinear interaction between the first two "
            "features; retain the useful linear signal as well."
        )
    if score < 0.97:
        return (
            "The main interaction looks right. Check whether weaker signed corrections involving "
            "x3 and x0 explain the remaining validation errors."
        )
    return (
        f"Round {round_index} reaches the target region. Verify the rule on the supplied training "
        "data and avoid adding unnecessary complexity."
    )


def main() -> int:
    args = parse_args()
    try:
        module = load_solution(args.workspace)
        predict = getattr(module, "predict")
        examples = make_examples(args.split)
        correct = 0
        for features, label in examples:
            prediction = int(predict(features))
            if prediction not in {0, 1}:
                raise ValueError("predict must return 0 or 1")
            correct += prediction == label
        score = correct / len(examples)
        payload = {
            "score": score,
            "valid": True,
            "metrics": {"accuracy": score, "examples": len(examples)},
            "feedback": pi_feedback(score, args.round, args.split),
        }
    except Exception as exc:
        payload = {
            "score": 0.0,
            "valid": False,
            "metrics": {},
            "feedback": f"The candidate could not be evaluated: {exc}",
            "error": str(exc),
        }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
