"""Live spend + health dashboard for a mini-CORAL API run.

Money comes from the local proxy's calls.jsonl (Perplexity returns
usage.cost per call -> exact dollars, no pricing tables). Health comes from
the run's trajectory logs and attempt records, so stagnation caused by
harness bugs (parse errors, crashes, restarts, idle agents, upstream errors)
is visible separately from genuine search plateau.

Usage:
    python scripts/cost_watch.py                  # follow latest run, 15s refresh
    python scripts/cost_watch.py --once           # single snapshot
    python scripts/cost_watch.py --budget 10      # warn past $10

Stdlib only; safe to run from any terminal while the run is live.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATUS_ORDER = ["improved", "baseline", "regressed", "crashed", "timeout"]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # mid-write line
    return out


def latest_run_dir(results: Path) -> Path | None:
    runs = sorted(results.glob("*/*/.coral"), key=lambda p: p.parent.name)
    return runs[-1].parent if runs else None


def parse_ts(iso: str) -> float:
    return dt.datetime.fromisoformat(iso).timestamp()


def fmt_dur(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1e6:.2f}M"
    if n >= 1_000:
        return f"{n / 1e3:.0f}k"
    return str(n)


def spend_block(calls: list[dict], budget: float | None) -> tuple[list[str], list[str]]:
    lines, warnings = [], []
    ok = [c for c in calls if "error" not in c]
    errs = [c for c in calls if "error" in c]
    cost = sum(c["cost"] for c in ok if c.get("cost") is not None)
    est = sum(c["cost"] for c in ok if c.get("cost") is not None and c.get("estimated"))
    missing = sum(1 for c in ok if c.get("cost") is None)
    ptok = sum(c.get("prompt_tokens", 0) for c in ok)
    ctok = sum(c.get("completion_tokens", 0) for c in ok)
    now = time.time()
    recent = [c for c in ok if c.get("ts", 0) > now - 600 and c.get("cost")]
    rate = sum(c["cost"] for c in recent) * 6  # last 10 min -> $/h
    line = (f"spend  ${cost:.4f}"
            + (f" (~${est:.4f} estimated)" if est else "")
            + f"   rate ${rate:.2f}/h (10m window)   "
            f"{len(ok)} calls, {fmt_tokens(ptok)} in / {fmt_tokens(ctok)} out")
    if budget is not None:
        pct = 100 * cost / budget if budget else 0
        line += f"   budget ${budget:.2f} [{pct:.0f}%]"
        if cost >= budget:
            warnings.append(f"BUDGET EXCEEDED: ${cost:.4f} >= ${budget:.2f}")
        elif cost >= 0.8 * budget:
            warnings.append(f"budget 80% reached (${cost:.4f} of ${budget:.2f})")
    lines.append(line)
    if missing:
        warnings.append(f"{missing} calls had no usage.cost (spend is an undercount)")
    if errs:
        last = errs[-1]
        warnings.append(f"{len(errs)} upstream errors via proxy "
                        f"(last: {last.get('error')} {last.get('detail', '')[:80]})")
    if ok:
        lines.append(f"last call  {fmt_dur(now - ok[-1]['ts'])} ago "
                     f"({ok[-1].get('dur', '?')}s, finish={ok[-1].get('finish')}, "
                     f"{fmt_tokens(ok[-1].get('prompt_tokens', 0))} in)")
    return lines, warnings


def run_block(run_dir: Path) -> tuple[list[str], list[str]]:
    lines, warnings = [], []
    now = time.time()

    run_events = read_jsonl(run_dir / "run.events.jsonl")
    started = next((e for e in run_events if e["type"] == "run_start"), None)
    stopped = next((e for e in run_events if e["type"] == "run_stop"), None)
    if started:
        elapsed = (parse_ts(stopped["ts"]) if stopped else now) - parse_ts(started["ts"])
        state = f"STOPPED ({stopped.get('reason')})" if stopped else "running"
        lines.append(f"run    {run_dir.name}  {state}  elapsed {fmt_dur(elapsed)}")

    attempts = []
    for p in sorted((run_dir / ".coral/public/attempts").glob("*.json")):
        try:
            attempts.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    scored = [a for a in attempts if a.get("score") is not None]
    best = max(scored, key=lambda a: a["score"], default=None)
    counts = {s: sum(1 for a in attempts if a.get("status") == s) for s in STATUS_ORDER}
    status_str = "  ".join(f"{s} {n}" for s, n in counts.items() if n)
    best_str = (f"best {best['score']:.4f} ({best['agent_id']})" if best else "best —")
    lines.append(f"evals  {len(attempts)}   {best_str}   {status_str or 'no attempts yet'}")

    # stagnation-vs-bug attribution: how many evals since the global best
    if best:
        after_best = [a for a in attempts if a["timestamp"] > best["timestamp"]]
        if len(after_best) >= 10:
            broken = sum(1 for a in after_best
                         if a.get("status") in ("crashed", "timeout"))
            kind = ("mostly crashes -> suspect harness/program bugs"
                    if broken > len(after_best) / 2 else
                    "scored-but-worse -> genuine search plateau")
            lines.append(f"stale  {len(after_best)} evals since best "
                         f"({broken} crashed/timeout: {kind})")

    for traj in sorted(run_dir.glob("logs/*.traj.jsonl")):
        ev = read_jsonl(traj)
        if not ev:
            continue
        agent = traj.stem.replace(".traj", "")
        turns = sum(1 for e in ev if e["type"] == "assistant")
        evals = sum(1 for e in ev if e["type"] == "eval")
        perr = sum(len(e.get("parse_errors") or []) for e in ev
                   if e["type"] == "assistant")
        errors = [e for e in ev if e["type"] == "error"]
        compactions = sum(1 for e in ev if e["type"] == "compaction")
        restarts = sum(1 for e in ev if e["type"] == "agent_restart")
        idle = now - parse_ts(ev[-1]["ts"])
        lines.append(
            f"  {agent}: turns {turns}, evals {evals}, idle {fmt_dur(idle)}"
            f"{f', parse_err {perr}' if perr else ''}"
            f"{f', errors {len(errors)}' if errors else ''}"
            f"{f', compactions {compactions}' if compactions else ''}"
            f"{f', restarts {restarts}' if restarts else ''}")
        if not stopped and idle > 600:
            warnings.append(f"{agent} idle {fmt_dur(idle)} "
                            "(grader hang? upstream stall?)")
        if errors:
            warnings.append(f"{agent} last error: {errors[-1].get('error', '')[:120]}")
        tail = [e for e in ev if e["type"] == "eval"][-4:]
        if len(tail) == 4 and all(e.get("status") in ("crashed", "timeout")
                                  for e in tail):
            warnings.append(f"{agent}: last 4 evals all crashed/timeout — "
                            "inspect its worktree program, may be a bug loop")
    return lines, warnings


def snapshot(calls_path: Path, run_dir: Path | None, budget: float | None) -> bool:
    """Print one dashboard frame; returns True when the run has stopped."""
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    print(f"\n=== mini-CORAL watch {stamp} " + "=" * 40)
    lines, warnings = spend_block(read_jsonl(calls_path), budget)
    done = False
    if run_dir is not None:
        rl, rw = run_block(run_dir)
        lines += rl
        warnings += rw
        done = any("STOPPED" in line for line in rl)
    else:
        lines.append("run    (none found yet)")
    for line in lines:
        print(line)
    for w in warnings:
        print(f"  !! {w}")
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--calls", type=Path, default=ROOT / "proxy_logs/calls.jsonl")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--run-dir", type=Path, default=None,
                    help="specific run dir (default: latest under --results)")
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--budget", type=float, default=None,
                    help="warn when total spend crosses this many dollars")
    ap.add_argument("--once", action="store_true")
    ns = ap.parse_args()

    while True:
        run_dir = ns.run_dir or latest_run_dir(ns.results)
        done = snapshot(ns.calls, run_dir, ns.budget)
        if ns.once or done:
            return 0
        time.sleep(ns.interval)


if __name__ == "__main__":
    raise SystemExit(main())
