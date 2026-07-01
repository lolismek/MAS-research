"""Lightweight read-only viewer for DyLAN (G-Memory) runs.

Self-contained: Python stdlib ONLY (http.server), no deps, no writes, touches
nothing in the harness. dylan writes ONE freeform artifact per run —
  dylan/.db/<model>/<task>/dylan/<mem>/total_task.log
— so this parses that log into structured runs (config, the DyLAN neuron grid, the
per-step Act/Obs trajectory, reward, tokens, price) and renders them. The per-neuron
LLM calls and Qwen3.6's <think> reasoning (stripped from replies by the proxy) are
recovered best-effort from shared/proxy/{calls,raw_calls}.jsonl by joining on the
run's [start,end] wall-clock window + model (the log carries no run tag).

Run (from repo root):
  python dylan/viewer/serve.py                 # serves http://127.0.0.1:8771
  DYLAN_VIEWER_PORT=9002 python dylan/viewer/serve.py
Then open the URL. Refresh to pick up new runs (the .db dir is scanned live).
"""
import html
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                         # dylan/
REPO_ROOT = os.path.dirname(ROOT)
DB = os.path.join(ROOT, ".db")
CALLS = os.path.join(REPO_ROOT, "shared", "proxy", "calls.jsonl")
RAW = os.path.join(REPO_ROOT, "shared", "proxy", "raw_calls.jsonl")
PORT = int(os.environ.get("DYLAN_VIEWER_PORT", sys.argv[1] if len(sys.argv) > 1 else "8771"))

BENCH_TITLE = {"fever": "FEVER", "pddl": "PDDL", "alfworld": "ALFWorld",
               "sciworld": "ScienceWorld"}
BENCH_ORDER = ["fever", "pddl", "alfworld", "sciworld"]

# ------------------------------------------------------------------- styles ----
CSS = """
*{box-sizing:border-box} body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
margin:0;background:#0f1115;color:#e5e7eb} a{color:#60a5fa;text-decoration:none}
a:hover{text-decoration:underline} .wrap{max-width:1180px;margin:0 auto;padding:24px}
.nav{position:sticky;top:0;background:#0f1115;padding:10px 0;border-bottom:1px solid #1f2430;
margin-bottom:8px;z-index:5} .nav a{margin-right:14px;font-size:13px}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;color:#9ca3af;margin:24px 0 8px;
text-transform:uppercase;letter-spacing:.5px} .muted{color:#9ca3af;font-size:13px}
.ob{display:inline-block;min-width:86px;text-align:center;padding:1px 8px;border-radius:10px;
font-size:11px;font-weight:700;color:#0f1115}
table{width:100%;border-collapse:collapse;margin:8px 0} th,td{text-align:left;
padding:7px 10px;border-bottom:1px solid #1f2430} th{color:#9ca3af;font-weight:600;
font-size:12px;text-transform:uppercase} tr:hover td{background:#151922}
td.num,th.num{text-align:right;font:12px/1.4 ui-monospace,Menlo,monospace}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;
background:#1f2937;color:#cbd5e1;margin:0 4px 4px 0} .pill b{color:#93c5fd}
.card{border:1px solid #232a36;border-radius:8px;padding:14px;margin:12px 0;background:#141821}
.mono{font:12px/1.4 ui-monospace,Menlo,monospace}
.grid{display:flex;flex-direction:column;gap:8px;margin:10px 0}
.round{display:flex;align-items:stretch;gap:8px;flex-wrap:wrap}
.rlab{min-width:66px;color:#6b7280;font-size:11px;text-transform:uppercase;
display:flex;align-items:center;letter-spacing:.5px}
.node{flex:1;min-width:150px;border:1px solid #2b3340;border-radius:8px;padding:8px 10px;
background:#161b25} .node.dec{border-color:#4c3f7a;background:#16121f}
.node.rank{border-color:#553c0c;background:#1a1305}
.role{font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#93c5fd}
.node.dec .role{color:#c4b5fd} .node.rank .role{color:#fcd34d}
.step{border:1px solid #232a36;border-radius:8px;margin:10px 0;overflow:hidden}
.stephead{background:#161b25;padding:6px 12px;font-size:12px;color:#9ca3af;
display:flex;justify-content:space-between}
.act{padding:8px 12px;background:#0d1320;border-left:3px solid #2563eb;
font:13px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word}
.obs{padding:8px 12px;background:#11151d;border-left:3px solid #333;
font:13px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word;color:#cbd5e1}
.obs.bad{border-left-color:#f87171} .obs.good{border-left-color:#34d399}
details{margin:6px 0} summary{cursor:pointer;color:#9ca3af;font-size:12px;user-select:none}
summary:hover{color:#cbd5e1}
.content{white-space:pre-wrap;word-break:break-word;font:13px/1.5 ui-monospace,Menlo,monospace;
padding:8px 12px;background:#11151d;border-radius:6px;margin:6px 0}
.think{border-left:3px dashed #7c3aed;background:#16121f}
.msg{border-left:3px solid #333;border-radius:4px;padding:8px 12px;margin:8px 0;background:#11151d}
.msg.system{border-left-color:#6b7280} .msg.user{border-left-color:#2563eb}
.msg.assistant{border-left-color:#059669}
.calls{width:100%;border-collapse:collapse;font:12px/1.4 ui-monospace,Menlo,monospace}
.calls td,.calls th{padding:4px 8px;border-bottom:1px solid #1f2430}
.dot{color:#a78bfa} .warn{color:#fbbf24}
.flow2{display:flex;align-items:stretch;flex-wrap:wrap;margin:12px 0}
.col{border:1px solid #2b3340;border-radius:8px;padding:8px 8px 4px;background:#12161f;
min-width:150px;flex:1} .col.term{background:#141821}
.collab{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#9ca3af;
margin-bottom:6px;text-align:center} .colsub{font-size:10px;color:#6b7280;text-transform:none;
letter-spacing:0;font-weight:400;margin-top:2px}
.arrow2{display:flex;flex-direction:column;align-items:center;justify-content:center;
padding:0 6px;color:#7c3aed;font-size:20px} .arrlab{font-size:9px;color:#8b7bb8;text-align:center}
.cap{border-left:3px solid #7c3aed;background:#16121f;border-radius:6px;padding:10px 13px;
margin:12px 0;font-size:13px;line-height:1.65;color:#cbd5e1} .cap b{color:#c4b5fd}
.crole{font-size:11px;font-weight:700} .r-solo{color:#60a5fa} .r-peers{color:#a78bfa}
.r-decision{color:#fbbf24} .r-ranker{color:#fb923c}
"""


def esc(s):
    return html.escape(str(s) if s is not None else "")


def page(title, body):
    return ("<!doctype html><html><head><meta charset=utf-8>"
            f"<title>{esc(title)}</title><style>{CSS}</style></head>"
            f"<body><div class=wrap>{body}</div></body></html>").encode()


def reward_badge(r, done):
    if r is None:
        return "#94a3b8", "N/A"
    if r >= 0.999:
        return "#34d399", "SOLVED 1.0"
    if r > 0:
        return "#fbbf24", f"PARTIAL {r:g}"
    return "#f87171", "reward 0"


# --------------------------------------------------------------- log parsing ---
TS_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) - (.*)$", re.S)
AGENT_RE = re.compile(r"^-+ MAS Agent: (\S+) -+\s*$")
TASK_RE = re.compile(r"^-+ Task: (\d+) -+\s*$")
ACT_RE = re.compile(r"^Act (\d+):\s*(.*)$", re.S)
NODE_RE = re.compile(r"^solver_(\d+)_(\d+)$")

TASK_TITLE_PATTERNS = [
    re.compile(r"Claim:\s*(.+)"),
    re.compile(r"Your task is to:\s*(.+)"),
    re.compile(r"\*\*Here is your task:\s*(.+)"),
    re.compile(r"following task:\s*\n+\s*(.+)"),
]


def _epoch(ts_str):
    try:
        return time.mktime(time.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def _messages(path):
    """Group the log's lines into (epoch, text) messages: a line with a timestamp
    starts a new message; unprefixed lines are continuations (multi-line log calls)."""
    msgs = []
    cur_ts, cur = None, []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = TS_RE.match(line)
            if m:
                if cur:
                    msgs.append((cur_ts, "\n".join(cur)))
                cur_ts, cur = _epoch(m.group(1)), [m.group(2)]
            else:
                cur.append(line)
    if cur:
        msgs.append((cur_ts, "\n".join(cur)))
    return msgs


def _norm_model(m):
    """Aliased .db dir name ('qwen2.5-14b') vs the proxy's full model string
    ('Qwen/Qwen2.5-14B-Instruct') — normalize the latter to match the former."""
    m = (m or "").split("/")[-1].lower()
    for suf in ("-instruct", "-chat", "-it"):
        m = m.replace(suf, "")
    return m


def _extract_title(text):
    # The real task sits after the "Your Turn" header; earlier few-shots carry decoy
    # "Claim:"/"task" lines, so anchor the search to the last such header.
    seg = text
    for anchor in ("Your Turn: Take Action!", "following task:"):
        i = text.rfind(anchor)
        if i != -1:
            seg = text[i:]
            break
    for pat in TASK_TITLE_PATTERNS:
        m = pat.search(seg)
        if m:
            return m.group(1).strip().split("\n")[0][:200]
    return None


def parse_log(path):
    rel = os.path.relpath(path, DB)
    parts = rel.split(os.sep)                 # <model>/<task>/<mas>/<mem>/total_task.log
    model = parts[0] if len(parts) > 0 else "?"
    task = parts[1] if len(parts) > 1 else "?"
    mem = parts[3] if len(parts) > 3 else "?"
    run = {"path": path, "rel": rel, "model": model, "task": task, "mem": mem,
           "config": {}, "agents": [], "tasks": [], "totals": {},
           "ts0": None, "ts1": None, "mtime": os.path.getmtime(path)}

    msgs = _messages(path)
    tss = [t for t, _ in msgs if t]
    if tss:
        run["ts0"], run["ts1"] = min(tss), max(tss)

    cur_task = None
    prev_agent = None
    for ts, text in msgs:
        head = text.split("\n", 1)[0].strip()

        mt = TASK_RE.match(head)
        if mt:
            cur_task = {"id": int(mt.group(1)), "title": None, "prompt": "", "traj": [],
                        "outcome": [], "reward": None, "done": None}
            run["tasks"].append(cur_task)
            prev_agent = None
            continue

        ma = AGENT_RE.match(head)
        if ma:
            prev_agent = ma.group(1)
            if prev_agent not in [a["name"] for a in run["agents"]]:
                run["agents"].append({"name": prev_agent, "instruction": ""})
            continue

        if prev_agent is not None:              # this message is prev_agent's instruction
            for a in run["agents"]:
                if a["name"] == prev_agent and not a["instruction"]:
                    a["instruction"] = text
                    if cur_task and not cur_task["title"]:
                        cur_task["title"] = _extract_title(text)
            prev_agent = None
            continue

        # standalone task prompt (few-shots + "Your Turn: ... <task>"), logged once
        if cur_task is not None and ("Your Turn: Take Action!" in text or "## Successful Examples" in text):
            cur_task["prompt"] = text
            ttl = _extract_title(text)
            if ttl:
                cur_task["title"] = ttl
            continue

        # config block (may be multi-line)
        for line in text.split("\n"):
            cm = re.match(r"(Node Number|Round Number|Roles|Use Critic|Learning Rate|"
                          r"Successful Topk|Failed Topk|Insights Topk)\s*:\s*(.+)", line.strip())
            if cm:
                run["config"][cm.group(1)] = cm.group(2).strip()

        mact = ACT_RE.match(head)
        if mact and cur_task is not None:
            action = mact.group(1) and mact.group(2).strip()
            obs = ""
            body = text.split("\n", 1)
            if len(body) > 1:
                obs = body[1]
            obs = re.sub(r"^Obs \d+:\s*", "", obs.strip())
            cur_task["traj"].append({"n": int(mact.group(1)), "act": action, "obs": obs})
            continue

        if cur_task is not None:
            if head.startswith(("You failed", "You have succeed", "Answer is",
                                "reward:", "rs:", "cnts:", "done:")):
                cur_task["outcome"].append(head)
            rm = re.search(r"reward:\s*([\d.]+)", text)
            if rm:
                cur_task["reward"] = float(rm.group(1))
            rsm = re.search(r"rs:\s*\[([0-9.,\s]*)\]", text)     # alfworld logs rs:[...] not reward:
            if rsm and cur_task["reward"] is None:
                vals = [float(x) for x in rsm.group(1).split(",") if x.strip()]
                if vals:
                    cur_task["reward"] = max(vals)
            dm = re.search(r"\bdone:\s*(True|False)", text)
            if dm:
                cur_task["done"] = dm.group(1) == "True"

        tm = re.search(r"Total execution time:\s*([\d.]+)", text)
        if tm:
            run["totals"]["time"] = float(tm.group(1))
        pm = re.search(r"completion_tokens:(\d+),\s*prompt_tokens:(\d+),\s*price=([\d.]+)", text)
        if pm:
            run["totals"].update(completion=int(pm.group(1)), prompt=int(pm.group(2)),
                                 price=float(pm.group(3)))

    for t in run["tasks"]:               # last-resort reward from the outcome text
        if t["reward"] is None:
            joined = " ".join(t["outcome"]).lower()
            if "succeed" in joined:
                t["reward"] = 1.0
            elif "fail" in joined or "incorrect" in joined:
                t["reward"] = 0.0
    # run-level reward = mean of task rewards (smokes are 1 task)
    rs = [t["reward"] for t in run["tasks"] if t["reward"] is not None]
    run["reward"] = sum(rs) / len(rs) if rs else None
    run["done"] = any(t.get("done") for t in run["tasks"])
    return run


def discover_runs():
    runs = []
    if not os.path.isdir(DB):
        return runs
    for dirpath, _, files in os.walk(DB):
        if "total_task.log" in files:
            try:
                runs.append(parse_log(os.path.join(dirpath, "total_task.log")))
            except Exception as e:                 # never let one bad log kill the index
                runs.append({"path": os.path.join(dirpath, "total_task.log"),
                             "rel": os.path.relpath(dirpath, DB), "task": "?", "model": "?",
                             "error": str(e), "tasks": [], "totals": {}, "config": {},
                             "agents": [], "reward": None, "ts0": None, "ts1": None,
                             "mtime": os.path.getmtime(os.path.join(dirpath, "total_task.log"))})
    runs.sort(key=lambda r: r.get("mtime", 0), reverse=True)
    return runs


# ------------------------------------------------------- proxy calls join ------
_CALLS = None


def load_calls():
    global _CALLS
    if _CALLS is None:
        _CALLS = []
        if os.path.exists(CALLS):
            with open(CALLS, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        _CALLS.append(json.loads(line))
                    except Exception:
                        pass
    return _CALLS


def calls_for(run):
    if not run.get("ts0"):
        return []
    lo, hi = run["ts0"] - 3, (run["ts1"] or run["ts0"]) + 3
    out = [c for c in load_calls()
           if lo <= c.get("ts", 0) <= hi and _norm_model(c.get("model")) == run["model"]]
    out.sort(key=lambda c: c.get("ts", 0))
    return out


_RAW_INDEX = None


def raw_index():
    """Lazy {round(ts,3): byte-offset} over raw_calls.jsonl so a call's reasoning /
    messages load on click without rescanning 177MB each time."""
    global _RAW_INDEX
    if _RAW_INDEX is None:
        _RAW_INDEX = {}
        if os.path.exists(RAW):
            with open(RAW, "rb") as f:
                off = f.tell()
                line = f.readline()
                while line:
                    try:
                        ts = json.loads(line).get("ts")
                        if ts is not None:
                            _RAW_INDEX[round(ts, 3)] = off
                    except Exception:
                        pass
                    off = f.tell()
                    line = f.readline()
    return _RAW_INDEX


def raw_call(ts):
    off = raw_index().get(round(float(ts), 3))
    if off is None:
        return None
    with open(RAW, "rb") as f:
        f.seek(off)
        try:
            return json.loads(f.readline())
        except Exception:
            return None


def call_role(ts):
    """Infer a call's place in the DyLAN grid from its prompt: decision agent, ranker, a
    round-0 solver (no peers), or a later-round solver (its user prompt carries the upstream
    'Proposals from other agents' block that neuron._process_inputs injects)."""
    call = raw_call(ts)
    if not call:
        return "?"
    sysc = userc = ""
    for m in call.get("messages", []):
        r, ct = m.get("role"), str(m.get("content", ""))
        if r == "system":
            sysc += ct
        elif r == "user":
            userc += ct
    low = sysc.lower()
    if "decision agent" in low:
        return "decision"
    if "ranking" in low or "rank their correctness" in low:
        return "ranker"
    if "Proposals from other agents" in userc:
        return "solver · sees peers"
    return "solver · solo"


# ------------------------------------------------------------------ render -----
def nav(extra=""):
    return f"<div class=nav><a href='/'>◂ all runs</a>{extra}</div>"


def render_index():
    runs = discover_runs()
    body = ["<h1>DyLAN runs</h1>",
            "<div class=muted>vanilla empty-memory arm · parsed live from "
            "<span class=mono>dylan/.db/&lt;model&gt;/&lt;task&gt;/dylan/&lt;mem&gt;/total_task.log</span></div>"]
    by_bench = {}
    for r in runs:
        by_bench.setdefault(r["task"], []).append(r)
    order = [b for b in BENCH_ORDER if b in by_bench] + \
            [b for b in sorted(by_bench) if b not in BENCH_ORDER]
    if not runs:
        body.append("<p class=muted>No runs found under dylan/.db yet.</p>")
    for bench in order:
        body.append(f"<h2>{esc(BENCH_TITLE.get(bench, bench))}</h2>")
        body.append("<table><tr><th>task</th><th>outcome</th><th class=num>steps</th>"
                    "<th class=num>tasks</th><th class=num>tok (c/p)</th>"
                    "<th class=num>price</th><th class=num>wall</th><th>model · mem</th><th>when</th></tr>")
        for r in by_bench[bench]:
            if r.get("error"):
                body.append(f"<tr><td colspan=9 class=warn>⚠ {esc(r['rel'])}: {esc(r['error'])}</td></tr>")
                continue
            color, label = reward_badge(r["reward"], r["done"])
            t0 = r["tasks"][0] if r["tasks"] else {}
            title = t0.get("title") or f"{len(r['tasks'])} task(s)"
            tot = r["totals"]
            steps = sum(len(t["traj"]) for t in r["tasks"])
            when = time.strftime("%m-%d %H:%M", time.localtime(r["mtime"]))
            body.append(
                f"<tr><td><a href='/run?path={quote(r['rel'])}'>{esc(title)}</a></td>"
                f"<td><span class=ob style='background:{color}'>{esc(label)}</span></td>"
                f"<td class=num>{steps}</td><td class=num>{len(r['tasks'])}</td>"
                f"<td class=num>{tot.get('completion','?')}/{tot.get('prompt','?')}</td>"
                f"<td class=num>${tot.get('price',0):.3f}</td>"
                f"<td class=num>{tot.get('time',0):.0f}s</td>"
                f"<td class=muted>{esc(r['model'])} · {esc(r['mem'])}</td>"
                f"<td class=muted>{when}</td></tr>")
        body.append("</table>")
    return page("DyLAN runs", "".join(body))


def _node_box(a, cls=""):
    return (f"<details class='node {cls}'><summary><span class=role>{esc(a['name'])}</span></summary>"
            f"<div class=content>{esc(a['instruction'][:4000])}</div></details>")


def render_structure(run):
    """Feed-forward layered network: columns = rounds; each later round reads all of the
    previous round's answers (the debate); consensus short-circuits; a decision agent breaks
    ties. Drawn left-to-right with arrows + a plain-language caption of the per-step dynamics."""
    rounds, dec, rank = {}, None, None
    for a in run["agents"]:
        m = NODE_RE.match(a["name"])
        if m:
            rounds.setdefault(int(m.group(1)), []).append((int(m.group(2)), a))
        elif "deci" in a["name"]:
            dec = a
        elif "rank" in a["name"]:
            rank = a

    parts = ["<div class=flow2>"]
    ris = sorted(rounds)
    for k, ri in enumerate(ris):
        boxes = "".join(_node_box(a) for _, a in sorted(rounds[ri]))
        sub = "answer solo" if ri == 0 else f"read all round&nbsp;{ri - 1} outputs"
        parts.append(f"<div class=col><div class=collab>round {ri}<div class=colsub>{sub}</div></div>{boxes}</div>")
        if k < len(ris) - 1:
            parts.append("<div class=arrow2>▶<div class=arrlab>proposals</div></div>")
    parts.append("<div class=arrow2>▶<div class=arrlab>commit</div></div>")
    term = ["<div class='col term'><div class=collab>each step commits one action</div>",
            "<div class=node><span class=role style='color:#34d399'>consensus → majority</span>"
            "<div class=colsub>if the round agrees (no extra call)</div></div>"]
    if dec:
        term.append("<details class='node dec'><summary><span class=role>" + esc(dec["name"]) +
                    " <span class=colsub>only on disagreement</span></span></summary>"
                    f"<div class=content>{esc(dec['instruction'][:4000])}</div></details>")
    term.append("</div>")
    parts.append("".join(term))
    parts.append("</div>")

    nnodes = run["config"].get("Node Number", "?")
    if rank:
        parts.append(f"<div class=muted style='font-size:12px;margin:4px 0'>+ <b>{esc(rank['name'])}</b>"
                     f" — mid-network, ranks a round and deactivates its weakest node; active only when "
                     f"node_num&gt;2 (yours is {esc(nnodes)}, so it never fires).</div>")
    parts.append(
        "<div class=cap>This whole grid runs <b>once per environment step</b> (each Act→Obs below), then "
        "resets. Round&nbsp;0 nodes answer the task <b>independently</b>; every later round's nodes are fed "
        "the previous round's answers as <i>“proposals from other agents for this turn's next action”</i> and "
        "choose the next action — <b>that's the debate</b>, and it runs across rounds (nodes in the same round "
        "don't see each other). If a round's nodes <b>agree, it stops early</b> and takes that answer — later "
        "rounds and the decision agent never run. Only on <b>disagreement</b> does <b>final_decison</b> read "
        "all answers and commit one. The committed action hits the env; then the grid resets for the next "
        "step. <span class=muted>(In this run's easy steps the two round-0 solvers usually agreed, so round 1 "
        "and the decision agent stayed dark — see the per-call roles below.)</span></div>")
    return "".join(parts)


def render_run(rel):
    path = os.path.join(DB, rel)
    if not os.path.isfile(path) or os.path.commonpath([os.path.abspath(path), DB]) != DB:
        return page("not found", nav() + "<p class=warn>run not found</p>")
    run = parse_log(path)
    cfg = run["config"]
    color, label = reward_badge(run["reward"], run["done"])
    tot = run["totals"]
    t0 = run["tasks"][0] if run["tasks"] else {}

    pills = "".join(f"<span class=pill>{esc(k)} <b>{esc(v)}</b></span>" for k, v in cfg.items())
    head = [
        nav(f" &nbsp;·&nbsp; <span class=muted>{esc(run['rel'])}</span>"),
        f"<h1>{esc(BENCH_TITLE.get(run['task'], run['task']))} "
        f"<span class=ob style='background:{color}'>{esc(label)}</span></h1>",
        f"<div class=muted>{esc(run['model'])} · mem={esc(run['mem'])} · "
        f"{len(run['tasks'])} task(s) · {sum(len(t['traj']) for t in run['tasks'])} steps</div>",
        "<div class=card>",
        f"<div>{pills}</div>",
        f"<div class=muted style='margin-top:8px'>tokens "
        f"<b class=mono>{tot.get('completion','?')}</b> completion / "
        f"<b class=mono>{tot.get('prompt','?')}</b> prompt · price "
        f"<b class=mono>${tot.get('price',0):.4f}</b> · wall "
        f"<b class=mono>{tot.get('time',0):.1f}s</b></div>",
        "</div>",
        "<h2>DyLAN structure — feed-forward layered debate</h2>", render_structure(run),
    ]

    # tasks + trajectories
    body = []
    for t in run["tasks"]:
        tcolor, tlabel = reward_badge(t["reward"], t.get("done"))
        body.append(f"<h2>Task {t['id']} · <span class=ob style='background:{tcolor}'>{esc(tlabel)}</span></h2>")
        if t.get("title"):
            body.append(f"<div class=card><b>Task:</b> <span class=mono>{esc(t['title'])}</span></div>")
        if not t["traj"]:
            body.append("<p class=muted>No Act/Obs steps recorded.</p>")
        for st in t["traj"]:
            obs = st["obs"]
            ocls = ""
            low = obs.lower()
            if "incorrect" in low or "not valid" in low or "failed" in low:
                ocls = "bad"
            elif "correct" in low or "completed" in low or "succeed" in low:
                ocls = "good"
            body.append(
                f"<div class=step><div class=stephead><span>step {st['n']}</span></div>"
                f"<div class=act>▸ {esc(st['act'])}</div>"
                + (f"<div class='obs {ocls}'>{esc(obs[:4000])}</div>" if obs else "") +
                "</div>")
        if t["outcome"]:
            body.append("<div class=card class=muted>" +
                        "<br>".join(esc(o) for o in t["outcome"]) + "</div>")

    # proxy calls panel (best-effort)
    calls = calls_for(run)
    if calls:
        nrz = sum(1 for c in calls if c.get("has_reasoning"))
        rcls = {"solver · solo": "r-solo", "solver · sees peers": "r-peers",
                "decision": "r-decision", "ranker": "r-ranker"}
        rows = []
        prev = None
        for i, c in enumerate(calls):
            dt = c.get("ts", 0) - run["ts0"]
            role = call_role(c.get("ts"))
            # a fresh round-0 solver after a peers/decision call = a new env step -> rule above it
            sep = " style='border-top:2px solid #37507a'" if (
                role == "solver · solo" and prev and prev != "solver · solo") else ""
            prev = role
            rz = ("<a href='/reasoning?ts=" + quote(str(c.get("ts"))) +
                  "&back=" + quote(run["rel"]) + "'>●</a>") if c.get("has_reasoning") else ""
            rows.append(
                f"<tr{sep}><td>{i+1}</td>"
                f"<td class='crole {rcls.get(role,'')}'>{esc(role)}</td>"
                f"<td>+{dt:.1f}s</td><td>{c.get('dur',0):.1f}s</td>"
                f"<td>{c.get('prompt_tokens','?')}→{c.get('completion_tokens','?')}</td>"
                f"<td>{esc(c.get('finish',''))}</td><td class=dot>{rz}</td></tr>")
        head_calls = [
            "<h2>LLM calls "
            f"<span class=muted style='text-transform:none'>({len(calls)} joined by time+model · "
            "role inferred from each call's prompt · blue rule = new env step · "
            f"{nrz} carry &lt;think&gt;, click ● to load)</span></h2>",
            "<div class=card><table class=calls><tr><th>#</th><th>role</th><th>t</th><th>dur</th>"
            "<th>tok p→c</th><th>finish</th><th>think</th></tr>",
            "".join(rows), "</table></div>"]
    else:
        head_calls = ["<h2>LLM calls</h2><p class=muted>No proxy calls matched this run's "
                      "time window + model (older run, or proxy logs rotated).</p>"]

    # representative task instruction (few-shots etc.), collapsible
    instr = (t0.get("prompt") if t0 else "") or (run["agents"][-1]["instruction"] if run["agents"] else "")
    tail = []
    if instr:
        tail = ["<details><summary>full task prompt (few-shots + task) — "
                f"{len(instr)} chars</summary><div class=content>{esc(instr)}</div></details>"]

    return page(f"{run['task']} run", "".join(head + body + head_calls + tail))


def render_reasoning(ts, back):
    call = raw_call(ts)
    b = nav(f" &nbsp;·&nbsp; <a href='/run?path={quote(back)}'>◂ back to run</a>") if back else nav()
    if not call:
        return page("reasoning", b + "<p class=warn>no raw call found for ts=" + esc(ts) + "</p>")
    out = [b, f"<h1>call · <span class=muted style='text-transform:none'>{esc(call.get('tag',''))} · "
              f"{esc(call.get('model',''))}</span></h1>"]
    for m in call.get("messages", []):
        role = m.get("role", "?")
        out.append(f"<div class='msg {esc(role)}'><div class=role>{esc(role)}</div>"
                   f"<div class=content>{esc(str(m.get('content',''))[:8000])}</div></div>")
    reasoning = call.get("reasoning")
    if reasoning:
        out.append("<h2>&lt;think&gt; reasoning</h2>"
                   f"<div class='content think'>{esc(reasoning[:20000])}</div>")
    reply = call.get("reply", {})
    if isinstance(reply, dict) and reply.get("content"):
        out.append("<h2>reply (visible)</h2>"
                   f"<div class='msg assistant'><div class=content>{esc(reply['content'][:8000])}</div></div>")
    return page("reasoning", "".join(out))


# ------------------------------------------------------------------ server -----
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/":
                self._send(render_index())
            elif u.path == "/run":
                self._send(render_run(q.get("path", [""])[0]))
            elif u.path == "/reasoning":
                self._send(render_reasoning(q.get("ts", [""])[0], q.get("back", [""])[0]))
            elif u.path == "/favicon.ico":
                self._send(b"", 204)
            else:
                self._send(page("404", nav() + "<p>not found</p>"), 404)
        except Exception as e:
            self._send(page("error", f"<pre>{esc(repr(e))}</pre>"), 500)


if __name__ == "__main__":
    print(f"DyLAN run viewer → http://127.0.0.1:{PORT}  (reading {DB})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
