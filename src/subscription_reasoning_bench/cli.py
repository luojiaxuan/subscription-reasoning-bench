from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .adapters.codex import resolve_codex_binary
from .models import RunConfig
from .reporting import load_records, print_summary, summarize
from .research_reporting import summarize_research
from .research_runner import (
    load_research_matrix_config,
    run_research_matrix,
    run_research_task,
)
from .research_tasks import load_research_task, run_grader
from .runner import load_matrix_config, run_matrix, with_timeout
from .server import capabilities, serve
from .suites import download_bbeh_mini, generate_reasoning_gym, load_suite, suite_hash


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="srb", description="Subscription Reasoning Bench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="check CLI installation and subscription authentication")
    subparsers.add_parser("capabilities", help="show the supported capability matrix")

    suite_parser = subparsers.add_parser("suite", help="prepare or validate benchmark suites")
    suite_subparsers = suite_parser.add_subparsers(dest="suite_command", required=True)
    bbeh = suite_subparsers.add_parser("bbeh-mini", help="download pinned BBEH mini")
    bbeh.add_argument("--output", type=Path, default=Path("data/bbeh-mini.jsonl"))
    validate = suite_subparsers.add_parser("validate", help="validate a JSONL suite")
    validate.add_argument("path", type=Path)
    rg = suite_subparsers.add_parser("reasoning-gym", help="generate a pinned procedural suite")
    rg.add_argument("--dataset", action="append", required=True)
    rg.add_argument("--size", type=int, default=20)
    rg.add_argument("--seed", type=int, default=20260715)
    rg.add_argument("--config-json", default="{}")
    rg.add_argument("--output", type=Path, default=Path("data/reasoning-gym.jsonl"))

    run = subparsers.add_parser("run", help="run one model configuration")
    run.add_argument("--suite", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--provider", choices=["codex", "claude"], required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--effort", choices=["high", "xhigh", "max", "ultra"], required=True)
    run.add_argument("--speed", choices=["standard", "fast"], default="standard")
    run.add_argument("--protocol", choices=["strict", "orchestrated"], default="strict")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--seed", type=int, default=20260715)
    run.add_argument("--timeout", type=int, default=900)
    run.add_argument("--limit", type=int)
    run.add_argument("--keep-traces", action="store_true")

    matrix = subparsers.add_parser("matrix", help="run a paired randomized TOML matrix")
    matrix.add_argument("config", type=Path)
    matrix.add_argument("--limit", type=int)
    matrix.add_argument("--timeout", type=int)
    matrix.add_argument("--keep-traces", action="store_true")
    matrix.add_argument("--dry-run", action="store_true")

    research = subparsers.add_parser("research", help="run long-horizon executable research tasks")
    research_subparsers = research.add_subparsers(dest="research_command", required=True)
    research_validate = research_subparsers.add_parser(
        "validate", help="validate a research task manifest and both grader splits"
    )
    research_validate.add_argument("task", type=Path)
    research_run = research_subparsers.add_parser(
        "run", help="run one model configuration on one research task"
    )
    research_run.add_argument("task", type=Path)
    research_run.add_argument("--output", type=Path, required=True)
    research_run.add_argument("--workspace-root", type=Path, default=Path("runs/research-workspaces"))
    research_run.add_argument("--provider", choices=["codex", "claude"], required=True)
    research_run.add_argument("--model", required=True)
    research_run.add_argument(
        "--effort", choices=["high", "xhigh", "max", "ultra"], required=True
    )
    research_run.add_argument("--speed", choices=["standard", "fast"], default="standard")
    research_run.add_argument(
        "--protocol", choices=["strict", "orchestrated"], default="strict"
    )
    research_run.add_argument("--attempt", type=int, default=1)
    research_run.add_argument("--keep-traces", action="store_true")
    research_matrix = research_subparsers.add_parser(
        "matrix", help="run a paired randomized long-horizon TOML matrix"
    )
    research_matrix.add_argument("config", type=Path)
    research_matrix.add_argument("--keep-traces", action="store_true")
    research_matrix.add_argument("--dry-run", action="store_true")
    research_report = research_subparsers.add_parser(
        "report", help="aggregate finalized long-horizon research records"
    )
    research_report.add_argument("results", type=Path)
    research_report.add_argument("--json", action="store_true")
    research_report.add_argument("--output", type=Path)

    report = subparsers.add_parser("report", help="aggregate a result JSONL")
    report.add_argument("results", type=Path)
    report.add_argument("--json", action="store_true")
    report.add_argument("--output", type=Path)

    ui = subparsers.add_parser("ui", help="serve the local result dashboard")
    ui.add_argument("--results-dir", type=Path, default=Path("runs"))
    ui.add_argument("--host", default="127.0.0.1")
    ui.add_argument("--port", type=int, default=8765)
    return parser


def run_auth(command: list[str]) -> dict[str, object]:
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "detail": str(exc)}
    detail = process.stdout.strip() or process.stderr.strip()
    return {"ok": process.returncode == 0, "detail": detail}


def doctor() -> int:
    codex_binary = resolve_codex_binary()
    claude_binary = shutil.which("claude")
    result = {
        "codex": {
            "path": codex_binary if Path(codex_binary).exists() else shutil.which(codex_binary),
            "auth": run_auth([codex_binary, "login", "status"]),
        },
        "claude": {
            "path": claude_binary,
            "auth": run_auth([claude_binary, "auth", "status"]) if claude_binary else {"ok": False},
        },
        "capabilities": capabilities(),
        "entitlement_note": "model entitlement is verified on the first real run, not by spending quota in doctor",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["codex"]["path"] or result["claude"]["path"] else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "capabilities":
        print(json.dumps(capabilities(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "suite":
        if args.suite_command == "bbeh-mini":
            count = download_bbeh_mini(args.output)
            print(f"wrote {count} tasks to {args.output} (sha256={suite_hash(args.output)})")
            return 0
        if args.suite_command == "validate":
            tasks = load_suite(args.path)
            print(f"valid: {len(tasks)} tasks (sha256={suite_hash(args.path)})")
            return 0
        if args.suite_command == "reasoning-gym":
            config = json.loads(args.config_json)
            if not isinstance(config, dict):
                raise ValueError("--config-json must decode to an object")
            count = generate_reasoning_gym(args.dataset, args.output, args.size, args.seed, config)
            print(f"wrote {count} tasks to {args.output} (sha256={suite_hash(args.output)})")
            return 0
    if args.command == "run":
        config = RunConfig(
            args.provider, args.model, args.effort, args.speed, args.protocol, args.timeout
        )
        executed, skipped = run_matrix(
            args.suite,
            args.output,
            [config],
            args.repeats,
            args.seed,
            args.limit,
            args.keep_traces,
        )
        print(f"executed={executed} resumed={skipped} output={args.output}")
        return 0
    if args.command == "matrix":
        suite, output, configs, repeats, seed = load_matrix_config(args.config)
        if args.timeout:
            configs = with_timeout(configs, args.timeout)
        task_count = len(load_suite(suite)) if args.limit is None else min(args.limit, len(load_suite(suite)))
        if args.dry_run:
            print(f"suite={suite}\noutput={output}\nconfigs={len(configs)}\ntasks={task_count}\nrepeats={repeats}")
            for config in configs:
                print(config.label)
            print(f"planned_runs={len(configs) * task_count * repeats}")
            return 0
        executed, skipped = run_matrix(
            suite, output, configs, repeats, seed, args.limit, args.keep_traces
        )
        print(f"executed={executed} resumed={skipped} output={output}")
        return 0
    if args.command == "research":
        if args.research_command == "validate":
            task = load_research_task(args.task)
            with tempfile.TemporaryDirectory(prefix="srb-research-validate-") as temp_dir:
                workspace = Path(temp_dir) / "workspace"
                shutil.copytree(task.starter_dir, workspace)
                validation = run_grader(task, workspace, "validation", 0)
                test = run_grader(task, workspace, "test", 0)
            result = {
                "task_id": task.id,
                "title": task.title,
                "digest": task.digest,
                "max_rounds": task.max_rounds,
                "min_rounds": task.min_rounds,
                "round_timeout_seconds": task.round_timeout_seconds,
                "declared_baseline_score": task.baseline_score,
                "declared_validation_baseline_score": task.validation_baseline_score,
                "starter_validation": validation.to_dict(),
                "starter_test": test.to_dict(),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if validation.valid and test.valid else 1
        if args.research_command == "run":
            task = load_research_task(args.task)
            config = RunConfig(
                args.provider,
                args.model,
                args.effort,
                args.speed,
                args.protocol,
                task.round_timeout_seconds,
            )
            record, skipped = run_research_task(
                task,
                config,
                output=args.output.resolve(),
                workspace_root=args.workspace_root.resolve(),
                attempt=args.attempt,
                keep_traces=args.keep_traces,
            )
            print(
                f"executed={int(not skipped)} resumed={int(skipped)} status={record['status']} "
                f"rounds={len(record['rounds'])} final_score={record['final_score']} "
                f"output={args.output}"
            )
            return 0
        if args.research_command == "matrix":
            tasks, output, workspace_root, configs, repeats, seed = load_research_matrix_config(
                args.config
            )
            if args.dry_run:
                max_rounds = sum(task.max_rounds for task in tasks) * len(configs) * repeats
                print(
                    f"tasks={len(tasks)}\noutput={output}\nworkspace_root={workspace_root}\n"
                    f"configs={len(configs)}\nrepeats={repeats}\nplanned_runs="
                    f"{len(tasks) * len(configs) * repeats}\nmax_research_rounds={max_rounds}"
                )
                for task in tasks:
                    print(f"task: {task.id} ({task.min_rounds}-{task.max_rounds} rounds)")
                for config in configs:
                    print(config.label)
                return 0
            executed, skipped = run_research_matrix(
                tasks,
                configs,
                output=output,
                workspace_root=workspace_root,
                repeats=repeats,
                seed=seed,
                keep_traces=args.keep_traces,
            )
            print(f"executed={executed} resumed={skipped} output={output}")
            return 0
        if args.research_command == "report":
            summary = summarize_research(load_records(args.results))
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            if args.json:
                print(json.dumps(summary, ensure_ascii=False, indent=2))
            else:
                print(
                    f"research_runs={summary['total_runs']} configs={summary['config_count']}"
                )
                for row in summary["configs"]:
                    print(
                        f"{row['label']} runs={row['runs']} final={row['final_score_mean']} "
                        f"normalized_gain={row['normalized_improvement_mean']} "
                        f"target_rate={row['target_reach_rate']}"
                    )
            return 0
    if args.command == "report":
        summary = summarize(load_records(args.results))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print_summary(summary)
        return 0
    if args.command == "ui":
        serve(args.results_dir, args.host, args.port)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
