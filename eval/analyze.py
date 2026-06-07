"""Aggregate results: per-mode survival (original vs new), task-success delta, cost.

Reads:
  results/tasks.jsonl
  results/judged/<uuid>/original.json          (re-judged original Magentic-One)
  results/judged/<uuid>/run_<r>.json           (re-judged new MAF runs)
  results/runs/<uuid>/<r>/{final_answer.txt, meta.json}   (new MAF arm)

Writes results/summary.{json,md}. Tolerates missing files (partial pilots).
Run: python eval/analyze.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
from grade import grade, extract_final_answer


def _load(p):
    return json.loads(p.read_text()) if p.exists() else None


def main():
    tasks = [json.loads(l) for l in open(C.TASKS_JSONL)]
    per_task, cost = [], {"mas_usd": 0.0, "judge_usd": 0.0}

    for t in tasks:
        u = t["uuid"]
        orig = _load(C.JUDGED_DIR / u / "original.json")
        runs = []
        for r in range(C.RUNS_PER_TASK):
            jr = _load(C.JUDGED_DIR / u / f"run_{r}.json")
            fa_p = C.RUNS_DIR / u / str(r) / "final_answer.txt"
            meta = _load(C.RUNS_DIR / u / str(r) / "meta.json")
            raw = fa_p.read_text(errors="ignore").strip() if fa_p.exists() else None
            # strip a leading "FINAL ANSWER:" if present (same extractor used on originals)
            new_answer = (extract_final_answer(raw) or raw) if raw else None
            new_pass = grade(new_answer, t["expected_answer"]) if new_answer else None
            if meta and meta.get("usage"):
                cost["mas_usd"] += meta["usage"].get("cost_usd", 0.0)
            if jr and jr.get("usage"):
                cost["judge_usd"] += jr["usage"]["cost_usd"]
            runs.append({"judge": jr, "new_pass": new_pass, "new_answer": new_answer})
        if orig and orig.get("usage"):
            cost["judge_usd"] += orig["usage"]["cost_usd"]
        per_task.append({"task": t, "orig": orig, "runs": runs})

    # objective task success (all originals failed by construction)
    new_passes = [r["new_pass"] for pt in per_task for r in pt["runs"] if r["new_pass"] is not None]
    new_success_rate = (sum(new_passes) / len(new_passes)) if new_passes else None

    # per-mode: among tasks the RE-JUDGED original flagged, how often is the new system flagged?
    mode_rows = []
    for m in C.MODES:
        orig_tasks = [pt for pt in per_task if pt["orig"] and pt["orig"]["modes"].get(m)]
        n_orig = len(orig_tasks)
        any_run, maj_run = 0, 0
        for pt in orig_tasks:
            flags = [r["judge"]["modes"].get(m, 0) for r in pt["runs"] if r["judge"]]
            if not flags:
                continue
            if sum(flags) >= 1:
                any_run += 1
            if sum(flags) > len(flags) / 2:
                maj_run += 1
        mode_rows.append({
            "mode": m, "orig_flagged_tasks": n_orig,
            "survive_any": (any_run / n_orig) if n_orig else None,
            "survive_majority": (maj_run / n_orig) if n_orig else None,
        })

    summary = {
        "n_tasks": len(tasks),
        "runs_per_task": C.RUNS_PER_TASK,
        "mas_model": C.MAS_MODEL,
        "judge_model": C.JUDGE_MODEL,
        "new_task_success_rate": new_success_rate,
        "cost": {**cost, "total_usd": cost["mas_usd"] + cost["judge_usd"]},
        "per_mode": mode_rows,
    }
    C.RESULTS.mkdir(exist_ok=True)
    C.SUMMARY_JSON.write_text(json.dumps(summary, indent=2))

    # markdown
    L = ["# Eval summary: MAF-Magentic vs MAST-GAIA failures", "",
         f"- MAS: `{C.MAS_MODEL}` | Judge: `{C.JUDGE_MODEL}` | {len(tasks)} tasks x {C.RUNS_PER_TASK} runs",
         f"- New task-success rate (originals all failed): "
         f"**{new_success_rate:.0%}**" if new_success_rate is not None else "- New task-success rate: n/a",
         f"- Cost: MAS ${cost['mas_usd']:.2f} + judge ${cost['judge_usd']:.2f} = "
         f"**${cost['mas_usd']+cost['judge_usd']:.2f}**", "",
         "## Per-mode survival (among originally-flagged tasks)", "",
         "| mode | name | orig-flagged | survive (any run) | survive (majority) |",
         "|---|---|---|---|---|"]
    from prompts import MODE_NAMES
    for row in summary["per_mode"]:
        sa = "-" if row["survive_any"] is None else f"{row['survive_any']:.0%}"
        sm = "-" if row["survive_majority"] is None else f"{row['survive_majority']:.0%}"
        star = " ⭐" if row["mode"] in ("2.4", "2.5") else (" (control)" if row["mode"] == "2.6" else "")
        L.append(f"| {row['mode']}{star} | {MODE_NAMES[row['mode']]} | "
                 f"{row['orig_flagged_tasks']} | {sa} | {sm} |")
    L += ["", "_⭐ = structural-core target (expect to persist); 2.6 = capability control "
          "(expect to drop)._"]
    C.SUMMARY_MD.write_text("\n".join(L))
    print("wrote", C.SUMMARY_JSON, "and", C.SUMMARY_MD)
    print("\n".join(L[:8]))


if __name__ == "__main__":
    main()
