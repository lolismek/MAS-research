"""mini-CORAL entry point: python -m minicoral {start,validate,status} -c task.yaml [-o override.yaml]"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

from .config import Config, load_config
from .grader import GraderRunner


def cmd_validate(cfg: Config) -> int:
    """Grade the seed code without launching agents (paper D.1 `coral validate`)."""
    grader_path = cfg.task.task_dir / "eval" / "grader.py"
    if not grader_path.exists():
        print(f"error: grader not found at {grader_path}", file=sys.stderr)
        return 2
    if not cfg.task.seed_dir.is_dir():
        print(f"error: seed dir not found at {cfg.task.seed_dir}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="minicoral-validate-") as tmp:
        code_dir = Path(tmp) / "code"
        shutil.copytree(cfg.task.seed_dir, code_dir)
        runner = GraderRunner(grader_path, timeout=cfg.grader.timeout, args=cfg.grader.args)
        result = asyncio.run(runner.grade(code_dir))

    print(f"task:      {cfg.task.name}")
    print(f"direction: {cfg.grader.direction}")
    print(f"score:     {result.score}")
    print(f"feedback:  {result.feedback}")
    if result.timed_out or result.crashed or result.score is None:
        print("validate: FAILED (seed must produce a valid score)", file=sys.stderr)
        return 1
    print("validate: OK")
    return 0


def _latest_run_dir(cfg: Config) -> Path | None:
    base = Path(cfg.run.results_dir)
    runs = sorted(base.glob("*/*/.coral"), key=lambda p: p.parent.name)
    return runs[-1].parent if runs else None


def cmd_status(cfg: Config) -> int:
    run_dir = _latest_run_dir(cfg)
    if run_dir is None:
        print(f"no runs found under {cfg.run.results_dir}/")
        return 1
    attempts_dir = run_dir / ".coral" / "public" / "attempts"
    attempts = []
    for p in sorted(attempts_dir.glob("*.json")):
        try:
            attempts.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    print(f"run: {run_dir}")
    print(f"attempts: {len(attempts)}")
    scored = [a for a in attempts if a.get("score") is not None]
    reverse = cfg.grader.direction == "maximize"
    scored.sort(key=lambda a: a["score"], reverse=reverse)
    print(f"{'score':>12}  {'status':<10} {'agent':<10} {'hash':<10} title")
    for a in scored[:20]:
        print(
            f"{a['score']:>12.6g}  {a['status']:<10} {a['agent_id']:<10} "
            f"{a['commit_hash'][:8]:<10} {a['title'][:60]}"
        )
    return 0


def cmd_start(cfg: Config, resolved_dump: bool = True) -> int:
    from .orchestrator import run_orchestrator

    return asyncio.run(run_orchestrator(cfg))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m minicoral")
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("start", "validate", "status"):
        p = sub.add_parser(name)
        p.add_argument("-c", "--config", required=True, type=Path, help="task.yaml")
        p.add_argument("-o", "--override", type=Path, default=None, help="override yaml")
    ns = ap.parse_args(argv)

    cfg = load_config(ns.config, ns.override)
    if ns.command == "validate":
        return cmd_validate(cfg)
    if ns.command == "status":
        return cmd_status(cfg)
    if ns.command == "start":
        return cmd_start(cfg)
    return 2


if __name__ == "__main__":
    sys.exit(main())
