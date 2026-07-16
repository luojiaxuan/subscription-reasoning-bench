from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRADER = PROJECT_ROOT / "examples/research-longloop-pilot/grader.py"


def run_grader(workspace: Path) -> dict[str, object]:
    process = subprocess.run(
        [
            sys.executable,
            str(GRADER),
            "--workspace",
            str(workspace),
            "--split",
            "validation",
            "--round",
            "1",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return json.loads(process.stdout)


def test_pilot_grader_blocks_main_module_target_reflection(tmp_path: Path) -> None:
    (tmp_path / "solution.py").write_text(
        "def predict(features):\n"
        "    import __main__\n"
        "    return __main__.target(features)\n",
        encoding="utf-8",
    )

    result = run_grader(tmp_path)

    assert result["valid"] is False
    assert result["score"] == 0.0
    assert "target" in str(result["error"])
