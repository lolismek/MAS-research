"""Process judges (P3) — the mechanism story, one judged axis per geometry (PLAN
"Metrics"):

  relay  -> INFORMATION SURVIVAL: are the caveats/uncertainties/evidence from the
            FIRST hand-off note that matter for the answer still visible in the
            final justification? (temporal loss = inherited conclusions shorn of
            their uncertainty)
  hub    -> CONTRADICTION-AT-MERGE: do worker reports rest on incompatible auxiliary
            assumptions (entity resolution, units, time frames, source choice), and
            did the merge SURFACE the conflict or silently absorb it?

Line-oriented judge outputs (the harness's own sentinel discipline), parsed
leniently; each run dir gets a judge.json; the summary prints per (topology, arm,
bench) cell.

VALIDATION CAVEAT (PLAN "Known risks"): judge numbers are not trusted until the
judge is validated on a hand-labeled slice — run with --sample N first, hand-check
the printed verdicts, THEN believe cell-level aggregates. The default judge model is
the same Qwen the agents use (self-judging); point JUDGE_BASE_URL/JUDGE_MODEL/
JUDGE_API_KEY at a stronger model for the real pass.

Usage (from repo root; proxy running for the default judge):
  conda run -n autogen_gc python duet/metrics/judge.py --topology relay
  conda run -n autogen_gc python duet/metrics/judge.py --topology hub --arm vanilla
  conda run -n autogen_gc python duet/metrics/judge.py --sample 5      # validation view
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                        # duet/
TRACES = os.path.join(ROOT, "traces")

JUDGE_BASE = os.environ.get("JUDGE_BASE_URL", "")   # default: shared proxy, tag duet_judge
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-4o")
JUDGE_KEY = os.environ.get("JUDGE_API_KEY", "dummy")
PROXY = os.environ.get("PROXY_URL", "http://127.0.0.1:8744/v1")
MAX_INPUT_CHARS = 24000

SURVIVAL_PROMPT = """You are auditing information loss in a worker hand-off.

A first worker investigated the task below, then wrote a hand-off note; other workers \
continued from that note alone and eventually a final answer was published.

<task>
{task}
</task>

<first_handoff_note>
{note}
</first_handoff_note>

<final_answer_and_justification>
{final}
</final_answer_and_justification>

Step 1 — from the NOTE only, list each caveat, uncertainty, or piece of evidence that \
MATTERS for deciding this task (skip filler; typically 1-5 items).
Step 2 — for each, judge whether it is still VISIBLE in the final answer/justification: \
'surfaced' (addressed, carried, or explicitly resolved) or 'dropped' (the final answer \
ignores it and does not resolve it).

Output one line per item, then a summary line, in exactly this form and nothing else:
ITEM: <short description> | surfaced
ITEM: <short description> | dropped
SURVIVAL: <n_surfaced>/<n_items>
If the note contains no substantive caveats or evidence, output exactly: SURVIVAL: 0/0"""

CONTRADICTION_PROMPT = """You are auditing a merge of independent workers' reports.

Workers investigated sub-questions of the task below BLIND to each other; a \
coordinator then merged their reports into the final answer.

<task>
{task}
</task>

<worker_reports>
{reports}
</worker_reports>

<merge_answer_and_justification>
{final}
</merge_answer_and_justification>

Step 1 — compare the reports' AUXILIARY ASSUMPTIONS: which entity each worker resolved \
names to, units, time frames, source choices. List each pair of reports that rest on \
INCOMPATIBLE assumptions (if any).
Step 2 — for each incompatibility, judge the merge: 'surfaced' (the merge names the \
conflict or resolves it explicitly) or 'absorbed' (the merge silently combines the \
conflicting findings).

Output one line per conflict, then a summary line, in exactly this form and nothing else:
CONFLICT: <worker_i vs worker_j: short description> | surfaced
CONFLICT: <worker_i vs worker_j: short description> | absorbed
CONTRADICTION: yes|no
If there are no incompatible assumptions, output exactly: CONTRADICTION: no"""

_ITEM_RE = re.compile(r"^\s*(?:ITEM|CONFLICT)\s*:\s*(.+?)\s*\|\s*(surfaced|dropped|absorbed)\s*$",
                      re.I | re.M)
_SURV_RE = re.compile(r"^\s*SURVIVAL\s*:\s*(\d+)\s*/\s*(\d+)", re.M)
_CONTRA_RE = re.compile(r"^\s*CONTRADICTION\s*:\s*(yes|no)", re.I | re.M)


def _client():
    from openai import OpenAI
    if JUDGE_BASE:
        return OpenAI(base_url=JUDGE_BASE, api_key=JUDGE_KEY)
    base, v1 = PROXY.rsplit("/", 1)
    return OpenAI(base_url=f"{base}/m/duet_judge/{v1}", api_key="dummy")


def _ask(client, prompt):
    r = client.chat.completions.create(
        model=JUDGE_MODEL, temperature=0.0, max_tokens=8000,
        messages=[{"role": "user", "content": prompt[:MAX_INPUT_CHARS]}])
    return r.choices[0].message.content or ""


def _read(rundir, name):
    p = os.path.join(rundir, name)
    return open(p).read() if os.path.exists(p) else ""


def _final_text(rundir):
    """The final agent's terminal text (answer + justification), from the transcript."""
    try:
        shifts = json.load(open(os.path.join(rundir, "transcript.json")))
        for m in reversed(shifts[-1]["transcript"]):
            if m.get("role") == "assistant" and m.get("content"):
                return m["content"]
    except Exception:
        pass
    r = json.load(open(os.path.join(rundir, "result.json")))
    return r.get("final_answer", "")


def judge_relay(client, rundir):
    notes = _read(rundir, "handoff_notes.txt")
    m = re.search(r"===== edge 1 =====\n(.*?)(?:\n===== |\Z)", notes, re.S)
    if not m:                                        # single-shift run: no edge, no loss
        return None
    reply = _ask(client, SURVIVAL_PROMPT.format(
        task=_read(rundir, "prompt.txt"), note=m.group(1).strip(),
        final=_final_text(rundir)))
    items = [dict(desc=d, verdict=v.lower()) for d, v in _ITEM_RE.findall(reply)]
    sm = _SURV_RE.search(reply)
    surfaced, total = (int(sm.group(1)), int(sm.group(2))) if sm else (
        sum(1 for i in items if i["verdict"] == "surfaced"), len(items))
    return dict(axis="information_survival", items=items, surfaced=surfaced,
                total=total, survival=(surfaced / total if total else None),
                judge_raw=reply)


def judge_hub(client, rundir):
    reports = _read(rundir, "reports.txt")
    if not reports.strip():
        return None
    reply = _ask(client, CONTRADICTION_PROMPT.format(
        task=_read(rundir, "prompt.txt"), reports=reports,
        final=_final_text(rundir)))
    items = [dict(desc=d, verdict=v.lower()) for d, v in _ITEM_RE.findall(reply)]
    cm = _CONTRA_RE.search(reply)
    contradiction = (cm.group(1).lower() == "yes") if cm else bool(items)
    absorbed = sum(1 for i in items if i["verdict"] == "absorbed")
    return dict(axis="contradiction_at_merge", items=items,
                contradiction=contradiction, n_conflicts=len(items),
                absorbed=absorbed, judge_raw=reply)


_JUDGES = {"relay": judge_relay, "hub": judge_hub}


def run_dirs(topology=None, arm=None):
    for root, _d, files in os.walk(TRACES):
        if "result.json" not in files:
            continue
        r = json.load(open(os.path.join(root, "result.json")))
        if topology and r.get("topology") != topology:
            continue
        if arm and r.get("arm") != arm:
            continue
        yield root, r


def main():
    args = sys.argv[1:]
    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default
    topology, arm = opt("--topology"), opt("--arm")
    sample, force = opt("--sample"), "--force" in args

    client = _client()
    cells, done = {}, 0
    for rundir, r in sorted(run_dirs(topology, arm)):
        topo = r.get("topology")
        if topo not in _JUDGES:
            continue
        jpath = os.path.join(rundir, "judge.json")
        if os.path.exists(jpath) and not force:
            j = json.load(open(jpath))
        else:
            j = _JUDGES[topo](client, rundir)
            if j is None:
                continue
            j.update(judge_model=JUDGE_MODEL, run=os.path.basename(rundir))
            with open(jpath, "w") as f:
                json.dump(j, f, indent=1)
        done += 1
        cells.setdefault((topo, r.get("arm"), r.get("bench")), []).append((r, j))
        if sample and done <= int(sample):
            print(f"\n--- {rundir}\n{j['judge_raw'][:1200]}")
        if sample and done >= int(sample):
            break

    print(f"\njudged {done} runs")
    for key in sorted(cells):
        rs = cells[key]
        print(f"\n== {key[0]} / {key[1]} / {key[2]} ==  n={len(rs)}")
        if key[0] == "relay":
            vals = [j["survival"] for _r, j in rs if j.get("survival") is not None]
            if vals:
                print(f"   information survival: mean {sum(vals)/len(vals):.2f} "
                      f"over {len(vals)} runs with caveats")
        else:
            n_c = sum(1 for _r, j in rs if j.get("contradiction"))
            n_a = sum(j.get("absorbed", 0) for _r, j in rs)
            print(f"   contradiction-at-merge: {n_c}/{len(rs)} runs; "
                  f"{n_a} conflicts silently absorbed")


if __name__ == "__main__":
    main()
