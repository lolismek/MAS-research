"""Driver: run the whole MAF-Magentic vs. MAST-GAIA experiment with LIVE progress.

For each task it prints, as it happens:
  - the task + gold + the ORIGINAL failure label (MAD cat2 modes + re-judged original)
  - each of R runs: the new answer, PASS/fail vs gold, the new judge's modes + a
    one-line analysis
  - a per-task rollup (success rate, which modes persisted vs dropped)
At the end: an aggregate per-mode survival table + total $ spent.

Resume-safe: reuses any cached MAS run / judge output, so you can Ctrl-C and re-run
(or run it again after a partial pass) without repeating or re-paying for work.

Run:  python eval/run_all.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
from grade import grade, extract_final_answer
from prompts import MODE_NAMES
import run_mas
import judge as J


def _load(p):
    return json.loads(p.read_text()) if p.exists() else None


def short(s, n=150):
    return " ".join(str(s or "").split())[:n]


def modes_on(jd):
    return [m for m, v in (jd or {}).get("modes", {}).items() if v]


def p(*a):
    print(*a, flush=True)            # flush so a backgrounded log updates live


def judge_original(t):
    out = C.JUDGED_DIR / t["uuid"] / "original.json"
    cached = _load(out)
    if cached:
        return cached, 0.0
    log = J._orig_console_log(t["uuid"], t["level"]).read_text(errors="ignore")
    res = J.judge_trace(log)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    return res, res["usage"]["cost_usd"]


def judge_run(t, r):
    out = C.JUDGED_DIR / t["uuid"] / f"run_{r}.json"
    cached = _load(out)
    if cached:
        return cached, 0.0
    tr = C.RUNS_DIR / t["uuid"] / str(r) / "transcript.txt"
    if not tr.exists():
        return None, 0.0
    res = J.judge_trace(tr.read_text(errors="ignore"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    return res, res["usage"]["cost_usd"]


def main():
    tasks = [json.loads(l) for l in open(C.TASKS_JSONL)]
    total = 0.0
    rollup = []          # (task, orig_judge, [run_judges], [passes])

    p(f"\nMAS={C.MAS_MODEL}  JUDGE={C.JUDGE_MODEL}  | {len(tasks)} tasks x {C.RUNS_PER_TASK} runs\n")

    for i, t in enumerate(tasks, 1):
        u = t["uuid"]
        p("=" * 84)
        p(f"[{i}/{len(tasks)}]  L{t['level']}  {u[:8]}   orig MAD cat2-modes: {t['orig_cat2_modes']}")
        p(f"  Q:    {short(t['prompt'], 120)}")
        p(f"  gold: {t['expected_answer']!r}")

        oj, c = judge_original(t); total += c
        p(f"  ORIGINAL (re-judged): success={oj['success']}  modes={modes_on(oj)}")
        p(f"     why: {short(oj.get('summary'), 170)}")

        run_judges, passes = [], []
        for r in range(C.RUNS_PER_TASK):
            run_mas.do_run(t, r)                               # resume-safe; prints its own line
            meta = _load(C.RUNS_DIR / u / str(r) / "meta.json")
            if meta and meta.get("usage"):
                total += meta["usage"].get("cost_usd", 0.0)
            fa = C.RUNS_DIR / u / str(r) / "final_answer.txt"
            raw = fa.read_text(errors="ignore").strip() if fa.exists() else ""
            ans = extract_final_answer(raw) or raw
            ok = bool(grade(ans, t["expected_answer"])) if ans else False
            passes.append(ok)
            jr, c = judge_run(t, r); total += c
            run_judges.append(jr)
            p(f"  RUN {r}: {'PASS' if ok else 'fail'}  ans={short(ans, 55)!r}"
              f"  new-modes={modes_on(jr)}")
            if jr:
                p(f"     why: {short(jr.get('summary'), 170)}")

        # per-task rollup: orig modes vs modes seen in ANY new run
        omodes = set(modes_on(oj))
        nmodes = set().union(*[set(modes_on(j)) for j in run_judges if j]) if run_judges else set()
        persisted = sorted(omodes & nmodes)
        dropped = sorted(omodes - nmodes)
        appeared = sorted(nmodes - omodes)
        p(f"  >> success {sum(passes)}/{len(passes)}  | persisted={persisted} "
          f"dropped={dropped} new={appeared}  | running ${total:.2f}")
        rollup.append((t, oj, run_judges, passes))

    # ---------------- aggregate survival table ----------------
    p("\n" + "=" * 84)
    p("AGGREGATE  (among tasks the RE-JUDGED ORIGINAL flagged for a mode: "
      "how often does the new system still get flagged?)")
    p(f"{'mode':5} {'name':34} {'orig#':>5} {'survive-any':>12} {'survive-maj':>12}")
    for m in C.MODES:
        flagged = [(oj, rj) for (_, oj, rj, _) in rollup if m in modes_on(oj)]
        n = len(flagged)
        if not n:
            continue
        any_cnt = maj_cnt = 0
        for oj, rj in flagged:
            f = [1 if m in modes_on(j) else 0 for j in rj if j]
            if not f:
                continue
            if sum(f) >= 1:
                any_cnt += 1
            if sum(f) > len(f) / 2:
                maj_cnt += 1
        star = " *" if m in ("2.4", "2.5") else (" (ctl)" if m == "2.6" else "")
        p(f"{m:5} {MODE_NAMES[m][:34]:34} {n:>5} "
          f"{any_cnt/n:>11.0%} {maj_cnt/n:>11.0%}{star}")

    npass = [ok for (_, _, _, ps) in rollup for ok in ps]
    p(f"\nnew task-success rate (all originals failed): "
      f"{sum(npass)}/{len(npass)} = {(sum(npass)/len(npass) if npass else 0):.0%}")
    p(f"TOTAL COST: ${total:.2f}")
    p("\n(* = structural-core target, expect to persist; (ctl) = capability control, "
      "expect to drop)")
    p("full machine-readable summary: run  python eval/analyze.py")


if __name__ == "__main__":
    main()
