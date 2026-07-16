from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=512)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([*(f"x{index}" for index in range(8)), "label"])
        for _ in range(args.rows):
            features = [rng.uniform(-1.0, 1.0) for _ in range(8)]
            writer.writerow([*(f"{value:.10f}" for value in features), target(features)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
