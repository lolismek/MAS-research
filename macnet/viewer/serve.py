"""Read-only viewer for MacNet add-on-arm traces.

Self-contained: Python stdlib ONLY (http.server), no deps, no writes, touches nothing
in the harness. It reads the durable trace store that macnet/viewer/ingest.py builds —
  macnet/traces/<arm>/<task>_off<N>/{total_task.log, calls.jsonl, raw_calls.jsonl, meta.json}
— parses the log for the Act/Obs trajectory + reward + cost, and reconstructs every LLM
call (what each node SEES / THINKS / OUTPUTS) from the tag-attributed proxy snapshots.

MacNet model: a "round" = one environment step. Within a step the graph runs in
topological order — solver_0 (proposes solo) -> solver_1 (sees upstream) -> decision
(commits the single action that hits the env). Add-on arms fire an extra extractor call
after each solver (voyager reflection / belief extraction) and/or inject a block into what
the downstream nodes see; those injections are highlighted in the SEES panel.

Run (from repo root):
  python macnet/viewer/serve.py                 # serves http://127.0.0.1:8772
  MACNET_VIEWER_PORT=9003 python macnet/viewer/serve.py
Then open the URL. Refresh to pick up newly-ingested runs (the traces dir is scanned live).
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
ROOT = os.path.dirname(HERE)                          # macnet/
TRACES = os.path.join(ROOT, "traces")
PORT = int(os.environ.get("MACNET_VIEWER_PORT", sys.argv[1] if len(sys.argv) > 1 else "8772"))

ARM_ORDER = ["vanilla", "full_memory", "memorybank", "metagpt", "voyager", "belief_state"]
ARM_BLURB = {
    "vanilla": "no add-on — the bare MacNet channel (control)",
    "full_memory": "shared &lt;scratchpad&gt; of every proposal this step",
    "memorybank": "scratchpad + Ebbinghaus forgetting (exp(-Δt/5)≥0.3)",
    "metagpt": "SOP system-prompt: action line 1 + WHY/EXPECTED",
    "voyager": "per-decision &lt;skill_library&gt; from a reflection call",
    "belief_state": "post-hoc ToM extractor → inline BELIEF: blurbs (needs proxy restart for real CoT)",
}
BENCH_TITLE = {"fever": "FEVER", "pddl": "PDDL", "alfworld": "ALFWorld", "sciworld": "ScienceWorld"}

# role -> (label, css class) for each reconstructed call
ROLE_META = {
    "solver-solo":    ("solver · proposes solo", "r-solo"),
    "solver-peers":   ("solver · sees upstream", "r-peers"),
    "decision":       ("decision · commits action", "r-decision"),
    "extract-voyager":("add-on · voyager reflection", "r-addon"),
    "extract-belief": ("add-on · belief extraction", "r-addon"),
    "?":              ("?", ""),
}

CSS = """
*{box-sizing:border-box} body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
margin:0;background:#0f1115;color:#e5e7eb} a{color:#60a5fa;text-decoration:none}
a:hover{text-decoration:underline} .wrap{max-width:1180px;margin:0 auto;padding:24px}
.nav{position:sticky;top:0;background:#0f1115;padding:10px 0;border-bottom:1px solid #1f2430;
margin-bottom:8px;z-index:5} .nav a{margin-right:14px;font-size:13px}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;color:#9ca3af;margin:24px 0 8px;
text-transform:uppercase;letter-spacing:.5px} .muted{color:#9ca3af;font-size:13px}
.mono{font:12px/1.4 ui-monospace,Menlo,monospace}
.ob{display:inline-block;min-width:86px;text-align:center;padding:1px 8px;border-radius:10px;
font-size:11px;font-weight:700;color:#0f1115}
table{width:100%;border-collapse:collapse;margin:8px 0} th,td{text-align:left;
padding:7px 10px;border-bottom:1px solid #1f2430} th{color:#9ca3af;font-weight:600;
font-size:12px;text-transform:uppercase} tr:hover td{background:#151922}
td.num,th.num{text-align:right;font:12px/1.4 ui-monospace,Menlo,monospace}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;
background:#1f2937;color:#cbd5e1;margin:0 4px 4px 0} .pill b{color:#93c5fd}
.card{border:1px solid #232a36;border-radius:8px;padding:14px;margin:12px 0;background:#141821}
.cap{border-left:3px solid #7c3aed;background:#16121f;border-radius:6px;padding:10px 13px;
margin:12px 0;font-size:13px;line-height:1.6;color:#cbd5e1} .cap b{color:#c4b5fd}
/* env step */
.step{border:1px solid #232a36;border-radius:8px;margin:14px 0;overflow:hidden}
.stephead{background:#161b25;padding:7px 12px;font-size:12px;color:#9ca3af;
display:flex;justify-content:space-between;align-items:center}
.act{padding:8px 12px;background:#0d1320;border-left:3px solid #2563eb;
font:13px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word}
.obs{padding:8px 12px;background:#11151d;border-left:3px solid #333;
font:13px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word;color:#cbd5e1}
.obs.bad{border-left-color:#f87171} .obs.good{border-left-color:#34d399}
.turns{padding:6px 10px 10px}
/* a node turn */
.turn{border:1px solid #2b3340;border-radius:8px;margin:8px 0;background:#12161f;overflow:hidden}
.turn>summary{cursor:pointer;padding:8px 12px;user-select:none;list-style:none;
display:flex;align-items:center;gap:10px;font-size:13px}
.turn>summary::-webkit-details-marker{display:none}
.turn[open]>summary{border-bottom:1px solid #1f2430;background:#141a24}
.badge{font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.4px;
padding:1px 8px;border-radius:10px;background:#1f2937}
.r-solo .badge{color:#60a5fa} .r-peers .badge{color:#a78bfa}
.r-decision .badge{color:#fbbf24} .r-addon .badge{color:#34d399}
.turn.r-decision{border-color:#4c3f7a} .turn.r-addon{border-color:#2f5d43}
.tmeta{color:#6b7280;font-size:11px;font:11px/1.4 ui-monospace,Menlo,monospace}
.panel{padding:8px 12px} .plab{font-size:10px;text-transform:uppercase;letter-spacing:.6px;
color:#6b7280;margin:8px 0 3px} .plab.sees{color:#60a5fa} .plab.thinks{color:#a78bfa}
.plab.out{color:#34d399}
.content{white-space:pre-wrap;word-break:break-word;font:12.5px/1.5 ui-monospace,Menlo,monospace;
padding:8px 12px;background:#0d1017;border-radius:6px;margin:2px 0;border:1px solid #1b2130}
.think{border-left:3px dashed #7c3aed} .out{border-left:3px solid #059669}
details.sys>summary{cursor:pointer;color:#6b7280;font-size:11px;margin:4px 0}
.inj{background:#0f2419;border:1px solid #2f6d49;border-radius:4px;padding:1px 3px;color:#a7f3d0}
.inj.native{background:#0d1c2e;border-color:#2b5688;color:#93c5fd}
.legend{font-size:11px;color:#6b7280;margin:2px 0 0} .legend .inj{padding:0 4px}
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
ACT_RE = re.compile(r"^Act (\d+):\s*(.*)$", re.S)


def _epoch(ts_str):
    try:
        return time.mktime(time.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def _messages(path):
    """Group the log's lines into (epoch, text): a timestamped line starts a message;
    unprefixed lines are continuations."""
    msgs, cur_ts, cur = [], None, []
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


def parse_log(path):
    """Trajectory (Act/Obs), reward and cost totals from a total_task.log."""
    traj, outcome, reward, done, totals = [], [], None, None, {}
    for ts, text in _messages(path):
        head = text.split("\n", 1)[0].strip()
        mact = ACT_RE.match(head)
        if mact:
            obs = text.split("\n", 1)
            obs = obs[1] if len(obs) > 1 else ""
            obs = re.sub(r"^Obs \d+:\s*", "", obs.strip())
            traj.append({"n": int(mact.group(1)), "act": mact.group(2).strip(), "obs": obs})
            continue
        if head.startswith(("You failed", "You have succeed", "Answer is",
                            "reward:", "rs:", "cnts:", "done:")):
            outcome.append(head)
        rsm = re.search(r"rs:\s*\[([0-9.,\s]*)\]", text)     # alfworld logs rs:[...]
        if rsm:
            vals = [float(x) for x in rsm.group(1).split(",") if x.strip()]
            if vals:
                reward = max(vals)
        rm = re.search(r"reward:\s*([\d.]+)", text)
        if rm and reward is None:
            reward = float(rm.group(1))
        dm = re.search(r"\bdone:\s*(True|False)", text)
        if dm:
            done = dm.group(1) == "True"
        tm = re.search(r"Total execution time:\s*([\d.]+)", text)
        if tm:
            totals["time"] = float(tm.group(1))
        pm = re.search(r"completion_tokens:(\d+),\s*prompt_tokens:(\d+),\s*price=([\d.]+)", text)
        if pm:
            totals.update(completion=int(pm.group(1)), prompt=int(pm.group(2)), price=float(pm.group(3)))
    if reward is None and outcome:
        joined = " ".join(outcome).lower()
        reward = 1.0 if "succeed" in joined else (0.0 if ("fail" in joined or "incorrect" in joined) else None)
    return {"traj": traj, "outcome": outcome, "reward": reward, "done": done, "totals": totals}


# ------------------------------------------------------- calls reconstruction ---
def _content(m):
    c = m.get("content")
    if isinstance(c, list):     # some providers use content parts
        return " ".join(str(p.get("text", p)) if isinstance(p, dict) else str(p) for p in c)
    return str(c or "")


def reply_text(call):
    r = call.get("reply")
    if isinstance(r, dict):
        return str(r.get("content") or "")
    return str(r or "")


def classify(raw):
    sysc = " ".join(_content(m) for m in raw.get("messages", []) if m.get("role") == "system")
    userc = " ".join(_content(m) for m in raw.get("messages", []) if m.get("role") == "user")
    low = sysc.lower()
    # extractor anchors FIRST — their bodies mention "decision agent" (the downstream reader),
    # which would otherwise collide with the decision check below.
    if "analyze one solver agent" in low:
        return "extract-belief"
    if "you are one solver on a team" in low:
        return "extract-voyager"
    if "you are the decision agent" in low:
        return "decision"
    sees = any(k in userc for k in ("Proposals from other agents", "shared_scratchpad",
                                    "skill_library", "Stated beliefs"))
    return "solver-peers" if sees else "solver-solo"


def load_calls(trace_dir):
    """Return the arm's calls, sorted by ts, each = merged compact(calls.jsonl) +
    full(raw_calls.jsonl), tagged with a reconstructed role."""
    raws = {}
    rp = os.path.join(trace_dir, "raw_calls.jsonl")
    if os.path.exists(rp):
        for line in open(rp, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
                raws[round(float(r["ts"]), 3)] = r
            except Exception:
                pass
    compact = {}
    cp = os.path.join(trace_dir, "calls.jsonl")
    if os.path.exists(cp):
        for line in open(cp, encoding="utf-8", errors="replace"):
            try:
                c = json.loads(line)
                compact[round(float(c["ts"]), 3)] = c
            except Exception:
                pass
    calls = []
    for ts in sorted(raws):
        raw, c = raws[ts], compact.get(ts, {})
        calls.append({
            "ts": ts, "role": classify(raw), "raw": raw,
            "sys": " ".join(_content(m) for m in raw.get("messages", []) if m.get("role") == "system"),
            "user": "\n".join(_content(m) for m in raw.get("messages", []) if m.get("role") == "user"),
            "reasoning": raw.get("reasoning") or "", "reply": reply_text(raw),
            "ptok": c.get("prompt_tokens"), "ctok": c.get("completion_tokens"),
            "dur": c.get("dur"), "finish": c.get("finish", ""),
        })
    return calls


def segment_steps(calls):
    """Split the flat call list into env steps; each step is the run of calls up to and
    including a decision call (the decision commits that step's action)."""
    steps, cur = [], []
    for c in calls:
        cur.append(c)
        if c["role"] == "decision":
            steps.append(cur)
            cur = []
    if cur:                 # trailing calls with no closing decision (truncated run)
        steps.append(cur)
    return steps


# ----------------------------------------------------------------- discovery ---
def discover_runs():
    runs = []
    if not os.path.isdir(TRACES):
        return runs
    for arm in sorted(os.listdir(TRACES)):
        adir = os.path.join(TRACES, arm)
        if not os.path.isdir(adir):
            continue
        for task in sorted(os.listdir(adir)):
            tdir = os.path.join(adir, task)
            meta_p = os.path.join(tdir, "meta.json")
            log_p = os.path.join(tdir, "total_task.log")
            if not (os.path.isfile(meta_p) and os.path.isfile(log_p)):
                continue
            try:
                meta = json.load(open(meta_p))
            except Exception:
                meta = {"arm": arm, "task": task}
            rel = os.path.relpath(tdir, TRACES)
            runs.append({"arm": meta.get("arm", arm), "task": meta.get("task", "?"),
                         "title": meta.get("title", ""), "tag": meta.get("tag", ""),
                         "rel": rel, "dir": tdir, "meta": meta,
                         "mtime": os.path.getmtime(log_p)})
    return runs


# ------------------------------------------------------------------- render ----
def nav(extra=""):
    return f"<div class=nav><a href='/'>◂ all runs</a>{extra}</div>"


def render_index():
    runs = discover_runs()
    body = ["<h1>MacNet add-on arms</h1>",
            "<div class=muted>within-round inter-node communication arms on the Tinker/Qwen3.6 proxy · "
            "parsed live from <span class=mono>macnet/traces/&lt;arm&gt;/&lt;task&gt;/</span></div>"]
    if not runs:
        body.append("<p class=muted>No traces yet. Build them with "
                    "<span class=mono>python macnet/viewer/ingest.py &lt;logs_dir&gt; &lt;tag_prefix&gt;</span>.</p>")
        return page("MacNet arms", "".join(body))

    by_task = {}
    for r in runs:
        by_task.setdefault(r["task"], []).append(r)
    for task, rs in by_task.items():
        title = rs[0].get("title") or ""
        body.append(f"<h2>{esc(BENCH_TITLE.get(task, task))}"
                    + (f" · <span class=mono style='text-transform:none'>{esc(title)}</span>" if title else "")
                    + "</h2>")
        body.append("<table><tr><th>arm</th><th></th><th>outcome</th><th class=num>steps</th>"
                    "<th class=num>calls</th><th class=num>tok c/p</th><th class=num>price</th>"
                    "<th class=num>wall</th></tr>")
        order = {a: i for i, a in enumerate(ARM_ORDER)}
        for r in sorted(rs, key=lambda x: order.get(x["arm"], 99)):
            log = parse_log(os.path.join(r["dir"], "total_task.log"))
            calls = load_calls(r["dir"])
            color, label = reward_badge(log["reward"], log["done"])
            tot = log["totals"]
            body.append(
                f"<tr><td><a href='/run?rel={quote(r['rel'])}'><b>{esc(r['arm'])}</b></a></td>"
                f"<td class=muted style='font-size:11px'>{ARM_BLURB.get(r['arm'],'')}</td>"
                f"<td><span class=ob style='background:{color}'>{esc(label)}</span></td>"
                f"<td class=num>{len(log['traj'])}</td>"
                f"<td class=num>{len(calls)}</td>"
                f"<td class=num>{tot.get('completion','?')}/{tot.get('prompt','?')}</td>"
                f"<td class=num>${tot.get('price',0):.3f}</td>"
                f"<td class=num>{tot.get('time',0):.0f}s</td></tr>")
        body.append("</table>")
    return page("MacNet arms", "".join(body))


INJ_TAGS = [("&lt;shared_scratchpad&gt;", "&lt;/shared_scratchpad&gt;"),
            ("&lt;skill_library&gt;", "&lt;/skill_library&gt;")]


def highlight_injections(escaped):
    """Wrap the add-on-injected regions of an already-escaped user prompt so they stand out
    from the base prompt. Add-on blocks (scratchpad/skills) green; the native MacNet
    'Proposals from other agents' spatial channel blue."""
    out = escaped
    for a, b in INJ_TAGS:
        out = re.sub(re.escape(a) + r".*?" + re.escape(b),
                     lambda m: f"<span class=inj>{m.group(0)}</span>", out, flags=re.S)
    # belief preamble + inline "Stated beliefs of Agent X:" lines
    out = re.sub(r"Some agent proposals below are annotated.*?(?=\n-{5,}|\n#|\Z)",
                 lambda m: f"<span class=inj>{m.group(0)}</span>", out, flags=re.S)
    out = re.sub(r"Stated beliefs of Agent[^\n]*(?:\n\s+- [^\n]*)*",
                 lambda m: f"<span class=inj>{m.group(0)}</span>", out, flags=re.S)
    # native spatial channel
    out = re.sub(r"# Proposals from other agents.*?(?=\nTreat these as advice|\Z)",
                 lambda m: f"<span class='inj native'>{m.group(0)}</span>", out, flags=re.S)
    return out


def render_turn(c, idx):
    label, cls = ROLE_META.get(c["role"], ("?", ""))
    meta = f"{c['ptok'] or '?'}→{c['ctok'] or '?'} tok"
    if c.get("dur"):
        meta += f" · {c['dur']:.1f}s"
    if c.get("finish"):
        meta += f" · {esc(c['finish'])}"
    think = c["reasoning"].strip()
    out = c["reply"].strip()
    sys_c = c["sys"].strip()
    user_h = highlight_injections(esc(c["user"]))
    parts = [f"<details class='turn {cls}'><summary>"
             f"<span class=badge>{esc(label)}</span>"
             f"<span class=tmeta>{esc(meta)}{' · ⟨think⟩' if think else ''}</span></summary>"]
    parts.append("<div class=panel>")
    parts.append("<div class='plab sees'>SEES — input prompt (add-on injections highlighted)</div>")
    if sys_c:
        parts.append(f"<details class=sys><summary>system prompt ({len(sys_c)} chars)</summary>"
                     f"<div class=content>{esc(sys_c[:8000])}</div></details>")
    parts.append(f"<div class=content>{user_h[:16000]}</div>")
    parts.append(f"<div class='plab thinks'>THINKS — &lt;think&gt; reasoning "
                 f"{'' if think else '(none captured)'}</div>")
    if think:
        parts.append(f"<div class='content think'>{esc(think[:16000])}</div>")
    parts.append("<div class='plab out'>OUTPUTS — visible reply</div>")
    parts.append(f"<div class='content out'>{esc(out[:8000]) or '<span class=muted>(empty)</span>'}</div>")
    parts.append("</div></details>")
    return "".join(parts)


def render_run(rel):
    tdir = os.path.join(TRACES, rel)
    if not os.path.isdir(tdir) or os.path.commonpath([os.path.abspath(tdir), TRACES]) != TRACES:
        return page("not found", nav() + "<p class=muted>run not found</p>")
    meta = json.load(open(os.path.join(tdir, "meta.json"))) if os.path.isfile(os.path.join(tdir, "meta.json")) else {}
    arm = meta.get("arm", "?")
    log = parse_log(os.path.join(tdir, "total_task.log"))
    calls = load_calls(tdir)
    steps = segment_steps(calls)
    color, label = reward_badge(log["reward"], log["done"])
    tot = log["totals"]

    other = [f"<a href='/run?rel={quote(os.path.join(a, os.path.basename(rel)))}'>{esc(a)}</a>"
             for a in ARM_ORDER
             if a != arm and os.path.isfile(os.path.join(TRACES, a, os.path.basename(rel), "meta.json"))]
    head = [
        nav("&nbsp;·&nbsp; switch arm: " + " ".join(other)),
        f"<h1>{esc(arm)} <span class=muted style='font-size:14px;text-transform:none'>on "
        f"{esc(BENCH_TITLE.get(meta.get('task'), meta.get('task','?')))}</span> "
        f"<span class=ob style='background:{color}'>{esc(label)}</span></h1>",
        f"<div class=muted>{ARM_BLURB.get(arm,'')} · task: <span class=mono>{esc(meta.get('title',''))}</span></div>",
        "<div class=card>",
        f"<span class=pill>tag <b>{esc(meta.get('tag',''))}</b></span>"
        f"<span class=pill>max_trials <b>{esc(meta.get('max_trials','?'))}</b></span>"
        f"<span class=pill>calls <b>{len(calls)}</b></span>"
        f"<span class=pill>steps <b>{len(log['traj'])}</b></span>"
        f"<span class=pill>tokens <b>{tot.get('completion','?')}c/{tot.get('prompt','?')}p</b></span>"
        f"<span class=pill>price <b>${tot.get('price',0):.4f}</b></span>"
        f"<span class=pill>wall <b>{tot.get('time',0):.1f}s</b></span>",
        "</div>",
        "<div class=cap>A <b>round = one environment step</b>. Within it the graph runs in topological "
        "order: <b>solver_0</b> proposes solo → <b>solver_1</b> sees solver_0's output (+ any add-on "
        "injection) → <b>decision</b> commits the single action that hits the env. Expand any node to see "
        "what it <b class=r-solo>SEES</b> / <b class=r-peers>THINKS</b> / <b class=r-addon>OUTPUTS</b>. "
        + (ARM_BLURB.get(arm, "") if arm != "vanilla" else "") +
        "<div class=legend>highlights in SEES: <span class=inj>add-on injection</span> "
        "<span class='inj native'>native \"proposals from other agents\" channel</span></div></div>",
    ]

    body = []
    n = max(len(log["traj"]), len(steps))
    for i in range(n):
        st = log["traj"][i] if i < len(log["traj"]) else None
        scalls = steps[i] if i < len(steps) else []
        act = st["act"] if st else "(no committed action logged)"
        obs = st["obs"] if st else ""
        ocls = ""
        low = obs.lower()
        if any(k in low for k in ("nothing happens", "not valid", "incorrect", "failed")):
            ocls = "bad"
        elif any(k in low for k in ("you open", "you pick", "you put", "correct", "succeed")):
            ocls = "good"
        body.append(f"<div class=step><div class=stephead><span>ENV STEP {i+1}</span>"
                    f"<span class=muted>{len(scalls)} node call(s)</span></div>"
                    f"<div class=act>▸ committed: {esc(act)}</div>"
                    + (f"<div class='obs {ocls}'>{esc(obs[:3000])}</div>" if obs else "")
                    + "<div class=turns>"
                    + "".join(render_turn(c, j) for j, c in enumerate(scalls))
                    + "</div></div>")
    if log["outcome"]:
        body.append("<div class=card muted>" + "<br>".join(esc(o) for o in log["outcome"]) + "</div>")
    return page(f"{arm} · {meta.get('task','')}", "".join(head + body))


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
                self._send(render_run(q.get("rel", [""])[0]))
            elif u.path == "/favicon.ico":
                self._send(b"", 204)
            else:
                self._send(page("404", nav() + "<p>not found</p>"), 404)
        except Exception as e:
            import traceback
            self._send(page("error", f"<pre>{esc(traceback.format_exc())}</pre>"), 500)


if __name__ == "__main__":
    print(f"MacNet arm viewer → http://127.0.0.1:{PORT}  (reading {TRACES})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
