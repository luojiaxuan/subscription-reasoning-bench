from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
from pathlib import Path


CANDIDATE_RUNNER = r"""
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

workspace = Path(sys.argv[1]).resolve(strict=True)
solution_path = (workspace / "solution.py").resolve(strict=True)
if workspace not in solution_path.parents:
    raise ValueError("solution path escaped the workspace")
payload = json.load(sys.stdin)
spec = importlib.util.spec_from_file_location("longloop_candidate_solution", solution_path)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load solution.py")
module = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(module)
    predict = getattr(module, "predict")
    predictions = [int(predict(features)) for features in payload["features"]]
print(json.dumps(predictions))
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--round", type=int, required=True)
    return parser.parse_args()


def evaluate_predictions(workspace: Path, features: list[list[float]]) -> list[int]:
    process = subprocess.run(
        [sys.executable, "-I", "-c", CANDIDATE_RUNNER, str(workspace.resolve(strict=True))],
        cwd=workspace.resolve(strict=True),
        input=json.dumps({"features": features}),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"candidate runner exited with {process.returncode}: {detail}")
    predictions = json.loads(process.stdout)
    if not isinstance(predictions, list) or len(predictions) != len(features):
        raise ValueError("candidate runner returned the wrong number of predictions")
    return [int(prediction) for prediction in predictions]


def target(features: list[float]) -> int:
    x0, x1, x2, x3, x4, x5, x6, x7 = features
    margin = (
        1.15 * x0 * x1
        - 0.95 * x2 * x3
        + 0.70 * x4
        + 0.55 * math.sin(math.pi * x5)
        - 0.40 * x6 * x6
        + 0.35 * x1 * x7
        - 0.25 * x0
        + 0.20 * math.cos(math.pi * x7)
        - 0.10
    )
    return int(margin > 0.0)


def make_examples(split: str) -> list[tuple[list[float], int]]:
    seed = 20260716 if split == "validation" else 20260717
    count = 700 if split == "validation" else 1200
    rng = random.Random(seed)
    examples = []
    for _ in range(count):
        features = [rng.uniform(-1.0, 1.0) for _ in range(8)]
        examples.append((features, target(features)))
    return examples


def pi_feedback(score: float, round_index: int, split: str) -> str:
    if split == "test":
        return ""
    if score < 0.70:
        return (
            "The current rule is near the one-feature baseline. Measure pairwise interactions "
            "and nonlinear transforms instead of relying on marginal correlations."
        )
    if score < 0.80:
        return (
            "Two strong signed interaction terms involve x0*x1 and x2*x3. Preserve the useful "
            "linear signal from x4 while testing them."
        )
    if score < 0.88:
        return (
            "The interaction structure is improving. Smooth nonlinear effects of x5 and x6 "
            "explain many remaining errors; compare sine-like and squared transforms."
        )
    if score < 0.94:
        return (
            "The major terms are present. Investigate weaker corrections involving x1*x7, x0, "
            "a periodic x7 term, and the decision intercept."
        )
    return (
        f"Round {round_index} is in the target region. Use the remaining budget to verify signs, "
        "relative coefficients, robustness, and unnecessary complexity."
    )


def main() -> int:
    args = parse_args()
    try:
        examples = make_examples(args.split)
        predictions = evaluate_predictions(
            args.workspace, [features for features, _ in examples]
        )
        correct = 0
        for prediction, (_, label) in zip(predictions, examples, strict=True):
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
