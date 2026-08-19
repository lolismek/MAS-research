"""Fact-survival: watch gold facts live or die on the relay channel, post-hoc.

For every persisted run and every edge j (the payload crossing from shift j to
shift j+1), and every gold item g of the task:

  available(g, j) = g appears anywhere in shifts 1..j's stored transcripts
                    (tool results, assistant text, recovered CoT, inherited
                    payload blocks — everything shift j could have carried
                    forward). NOTE the task prompt itself is part of the
                    transcript; for FanOutQA the gold items are looked-up
                    VALUES, not question text, so this barely inflates
                    availability — but it is a stated caveat, not a bug fix.
  survived(g, j)  = g appears in the edge-j payload (the note / rendered log).

Survival rate = P(survived | available), the direct measurement of information
death on the channel. Also reported: end-to-end delivery (available at the LAST
edge vs present in the final answer — recall conditioned on the chain having ever
held the fact), and the per-edge death curve.

Reads trace dirs written by run_task.py (both arms — the transcript arm is the
control curve, expected ~flat). Pure offline, no LLM.

  conda run -n autogen_gc python chainloss/metrics/fact_survival.py            # all traces
  ... fact_survival.py --details out.jsonl                                     # + per-item rows
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))

from scoring import gold_items, item_hit_in_text  # noqa: E402

TRACES = os.path.join(ROOT, "traces")


def _shift_text(shift):
    """Everything a shift's stored transcript holds, as one searchable text blob
    (system layer excluded — it is harness boilerplate, never facts)."""
    parts = []
    for m in shift.get("transcript") or []:
        if m.get("role") == "system":
            continue
        if m.get("content"):
            parts.append(str(m["content"]))
        if m.get("reasoning_content"):
            parts.append(str(m["reasoning_content"]))
        for tc in m.get("tool_calls") or []:
            parts.append(((tc.get("function") or {}).get("arguments")) or "")
    return "\n".join(parts)


def _payloads(rundir):
    for fname in ("handoff_notes.txt", "work_logs.txt"):
        p = os.path.join(rundir, fname)
        if os.path.exists(p):
            chunks = open(p).read().split("===== edge ")
            out = []
            for c in chunks[1:]:
                body = c.split("=====", 1)[-1]
                out.append(body.strip())
            return out
    return []


def _runs():
    for arm in sorted(os.listdir(TRACES)) if os.path.isdir(TRACES) else []:
        arm_dir = os.path.join(TRACES, arm)
        if not os.path.isdir(arm_dir):
            continue
        for root, _dirs, files in os.walk(arm_dir):
            if "result.json" in files:
                yield root


def analyze_run(rundir):
    res = json.load(open(os.path.join(rundir, "result.json")))
    edges = res.get("edges", 0)
    if edges == 0:
        return res, []                     # N=1: no channel to measure
    transcripts = json.load(open(os.path.join(rundir, "transcript.json")))
    payloads = _payloads(rundir)
    gold = gold_items(res["expected_answer"], res.get("answer_type", "freeform"))
    texts = [_shift_text(s) for s in transcripts]

    rows = []
    cum = ""
    for j in range(min(edges, len(payloads))):
        cum += "\n" + texts[j]             # everything shifts 1..j+1 held
        for g in gold:
            avail = item_hit_in_text(cum, g)
            rows.append(dict(run=rundir, arm=res["arm"], n=res["n"], edge=j + 1,
                             item=str(g)[:80], available=avail,
                             survived=item_hit_in_text(payloads[j], g) if avail else None,
                             in_final=item_hit_in_text(res.get("final_answer") or "", g)))
    return res, rows


def main():
    details_path = None
    args = sys.argv[1:]
    if "--details" in args:
        details_path = args[args.index("--details") + 1]

    all_rows = []
    n_runs = 0
    for rundir in _runs():
        try:
            _res, rows = analyze_run(rundir)
        except Exception as e:
            print(f"[skip {rundir}] {e!r}")
            continue
        n_runs += 1
        all_rows.extend(rows)

    if details_path:
        with open(details_path, "w") as f:
            for r in all_rows:
                f.write(json.dumps(r) + "\n")

    cells = {}
    for r in all_rows:
        cells.setdefault((r["arm"], r["n"]), []).append(r)
    print(f"{n_runs} runs, {len(all_rows)} (edge x item) rows\n")
    print("| arm | N | avail. rows | availability | survival P(in payload|avail) | "
          "delivery P(in final|avail at last edge) |")
    print("|---|---|---|---|---|---|")
    for (arm, n), rows in sorted(cells.items()):
        avail = [r for r in rows if r["available"]]
        surv = [r for r in avail if r["survived"]]
        last_edge = {}
        for r in avail:                    # last edge each (run,item) was available at
            key = (r["run"], r["item"])
            if key not in last_edge or r["edge"] > last_edge[key]["edge"]:
                last_edge[key] = r
        delivered = [r for r in last_edge.values() if r["in_final"]]
        f = lambda a, b: f"{a / b:.3f}" if b else "—"
        print(f"| {arm} | {n} | {len(avail)}/{len(rows)} | "
              f"{f(len(avail), len(rows))} | {f(len(surv), len(avail))} | "
              f"{f(len(delivered), len(last_edge))} |")

    # per-edge death curve (note arm): survival by edge index
    note_rows = [r for r in all_rows if r["arm"] == "note" and r["available"]]
    if note_rows:
        print("\nnote-arm survival by edge index (does the channel decay along the chain?):")
        by_edge = {}
        for r in note_rows:
            by_edge.setdefault((r["n"], r["edge"]), []).append(r)
        for (n, e), rows in sorted(by_edge.items()):
            s = sum(1 for r in rows if r["survived"])
            print(f"  n={n} edge {e}: {s}/{len(rows)} = {s / len(rows):.3f}")


if __name__ == "__main__":
    main()
