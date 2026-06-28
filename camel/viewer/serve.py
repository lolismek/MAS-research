"""Lightweight read-only viewer for CAMEL pipeline traces.

Self-contained: Python stdlib ONLY (http.server), no deps, no writes, touches
nothing in the harness. It just reads camel/traces/<arm>/<id>/run_N/{result,
transcript}.json and renders them. Qwen3.6's <think> reasoning (stripped from the
transcript by the proxy) is recovered best-effort from shared/proxy/raw_calls.jsonl
by matching the run's tag and aligning calls positionally to assistant turns.

Run (from repo root):
  python camel/viewer/serve.py            # serves http://127.0.0.1:8770
  CAMEL_VIEWER_PORT=9001 python camel/viewer/serve.py
Then open the URL. Refresh to pick up new runs (the dir is scanned live).
"""
import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                          # camel/
REPO_ROOT = os.path.dirname(ROOT)
TRACES = os.path.join(ROOT, "traces")
RAW = os.path.join(REPO_ROOT, "shared", "proxy", "raw_calls.jsonl")
PORT = int(os.environ.get("CAMEL_VIEWER_PORT", sys.argv[1] if len(sys.argv) > 1 else "8770"))

sys.path.insert(0, os.path.join(ROOT, "harness"))
import agg as _agg          # shared aggregation (dedup latest run + restrict to eval set)

ROLE_COLOR = {"system": "#6b7280", "user": "#2563eb",
              "assistant": "#059669", "tool": "#d97706"}

# 3-way Outcome (honesty axis): correct / abstained (honest UNKNOWN) / wrong_confident.
OUTCOME_COLOR = {"correct": "#34d399", "abstained": "#fbbf24", "wrong_confident": "#f87171"}
OUTCOME_LABEL = {"correct": "CORRECT", "abstained": "ABSTAINED", "wrong_confident": "WRONG"}

# Benchmarks, in display order; anything else falls into "other".
BENCH_ORDER = ["gaia", "gpqa_diamond", "math_l5", "smoke", "other"]
BENCH_TITLE = {"gaia": "GAIA", "gpqa_diamond": "GPQA-Diamond", "math_l5": "MATH level-5",
               "smoke": "smoke / plumbing", "other": "other"}


def bench_of(res):
    """The benchmark a run belongs to — from the `bench` field, else inferred from id."""
    b = res.get("bench")
    if b:
        return b if b in BENCH_TITLE else "other"
    tid = res.get("id", "")
    for pre, name in (("gaia_", "gaia"), ("gpqad", "gpqa_diamond"),
                      ("math_l5", "math_l5"), ("smoke", "smoke")):
        if tid.startswith(pre):
            return name
    return "other"


def outcome_display(res):
    """(label, color) for a run. Uses the 3-way outcome; falls back to exact_match
    for legacy traces written before the scorer existed."""
    o = res.get("outcome")
    if o:
        return OUTCOME_LABEL.get(o, o.upper()), OUTCOME_COLOR.get(o, "#9ca3af")
    ok = res.get("exact_match")
    return ("PASS" if ok else "FAIL"), ("#34d399" if ok else "#f87171")

CSS = """
*{box-sizing:border-box} body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
margin:0;background:#0f1115;color:#e5e7eb} a{color:#60a5fa;text-decoration:none}
a:hover{text-decoration:underline} .wrap{max-width:1180px;margin:0 auto;padding:24px}
.nav{position:sticky;top:0;background:#0f1115;padding:10px 0;border-bottom:1px solid #1f2430;
margin-bottom:8px;z-index:5} .nav a{margin-right:14px;font-size:13px}
.ob{display:inline-block;min-width:78px;text-align:center;padding:1px 8px;border-radius:10px;
font-size:11px;font-weight:700;color:#0f1115} .bsum{color:#9ca3af;font-size:12px;font-weight:400}
.mono{font:12px/1.4 ui-monospace,Menlo,monospace}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;color:#9ca3af;margin:24px 0 8px;
text-transform:uppercase;letter-spacing:.5px} .muted{color:#9ca3af;font-size:13px}
table{width:100%;border-collapse:collapse;margin:8px 0} th,td{text-align:left;
padding:7px 10px;border-bottom:1px solid #1f2430} th{color:#9ca3af;font-weight:600;
font-size:12px;text-transform:uppercase} tr:hover td{background:#151922}
.pass{color:#34d399;font-weight:700} .fail{color:#f87171;font-weight:700}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;
background:#1f2937;color:#cbd5e1;margin-right:4px}
.card{border:1px solid #232a36;border-radius:8px;padding:14px;margin:12px 0;background:#141821}
.flow{display:flex;align-items:stretch;gap:0;flex-wrap:wrap;margin:12px 0}
.node{flex:1;min-width:150px;border:1px solid #2b3340;border-radius:8px;padding:10px;
background:#161b25} .arrow{display:flex;align-items:center;padding:0 6px;color:#6b7280;
font-size:20px} .edge{font-size:10px;color:#a78bfa;text-align:center;margin-top:2px}
.role{font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.msg{border-left:3px solid #333;border-radius:4px;padding:8px 12px;margin:8px 0;background:#11151d}
.content{white-space:pre-wrap;word-break:break-word;font:13px/1.5 ui-monospace,Menlo,monospace}
.tcall{font:12px/1.4 ui-monospace,monospace;background:#1a1305;border:1px solid #553c0c;
border-radius:5px;padding:6px 9px;margin:6px 0;color:#fcd34d}
details{margin:6px 0} summary{cursor:pointer;color:#9ca3af;font-size:12px;user-select:none}
summary:hover{color:#cbd5e1} .think{border-left:3px dashed #7c3aed;background:#16121f}
.tool-out{background:#0c0a06} .prompt{background:#0d1320;border:1px solid #1e3a5f}
.agentbox{border:1px solid #232a36;border-radius:8px;margin:14px 0;overflow:hidden}
.agenthead{background:#161b25;padding:10px 14px;display:flex;justify-content:space-between;
align-items:center} .agentbody{padding:0 14px 4px}
"""


def esc(s):
    return html.escape(str(s) if s is not None else "")


def page(title, body):
    return ("<!doctype html><html><head><meta charset=utf-8>"
            f"<title>{esc(title)}</title><style>{CSS}</style></head>"
            f"<body><div class=wrap>{body}</div></body></html>").encode()


# --------------------------------------------------------------- discovery ----
def discover_runs():
    runs = []
    if not os.path.isdir(TRACES):
        return runs
    for arm in sorted(os.listdir(TRACES)):
        ad = os.path.join(TRACES, arm)
        if not os.path.isdir(ad):
            continue
        for tid in sorted(os.listdir(ad)):
            td = os.path.join(ad, tid)
            if not os.path.isdir(td):
                continue
            for rn in sorted(os.listdir(td)):
                rj = os.path.join(td, rn, "result.json")
                if os.path.exists(rj):
                    try:
                        res = json.load(open(rj))
                    except Exception:
                        res = {}
                    runs.append(dict(arm=arm, tid=tid, run=rn,
                                     rel=f"{arm}/{tid}/{rn}", res=res))
    return runs


def load_reasonings(tag):
    """Ordered list of <think> traces for this run's tag, from raw_calls.jsonl."""
    out = []
    if not os.path.exists(RAW):
        return out
    for line in open(RAW):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("tag") == tag:
            out.append(r.get("reasoning"))
    return out


# ----------------------------------------------------------------- render -----
def _short(s, n=44):
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[:n] + "…"


def _cost_str(res):
    c = res.get("cost_usd")
    return f"${c:.4f}" if isinstance(c, (int, float)) else "—"


def _o_cell(label, x, n, color):
    """A colored outcome cell: 'NN.N% (k)'."""
    p = (x / n * 100) if n else 0.0
    return (f"<td style='color:{color};font-weight:600'>{p:.1f}% "
            f"<span class=muted style='font-weight:400'>({x})</span></td>")


def _summ_row(title, d, bold=False):
    n = d["n"]
    nm = f"<b>{esc(title)}</b>" if bold else esc(title)
    avg = f"{d['seconds']/n:.0f}s" if n else "—"
    return (f"<tr><td>{nm}</td><td class=muted>{n}</td>"
            + _o_cell("correct", d["correct"], n, OUTCOME_COLOR["correct"])
            + _o_cell("wrong", d["wrong_confident"], n, OUTCOME_COLOR["wrong_confident"])
            + _o_cell("abstained", d["abstained"], n, OUTCOME_COLOR["abstained"])
            + f"<td class=muted>${d['cost']:.2f}</td><td class=muted>{avg}</td></tr>")


def render_summary():
    """Aggregate scoreboard at the top of the index: per arm × benchmark, deduped to
    the latest run per task and restricted to the official evaluated id set. Mirrors
    camel/RESULTS.md (same agg module), so the page and the doc never disagree."""
    arms = _agg.arms()
    if not arms:
        return ""
    cols = ("<tr><th>benchmark</th><th>n</th><th>correct</th><th>wrong-confident</th>"
            "<th>abstained</th><th>cost</th><th>avg time</th></tr>")
    blocks = ""
    for arm in arms:
        s = _agg.summarize(arm, restrict=True)
        tot = dict(n=0, correct=0, abstained=0, wrong_confident=0, cost=0.0, seconds=0.0)
        rows = ""
        for b, title in _agg.BENCHES:
            d = s[b]
            if not d["n"]:
                continue
            for k in tot:
                tot[k] += d[k]
            rows += _summ_row(title, d)
        if not tot["n"]:
            continue
        rows += _summ_row("Total", tot, bold=True)
        blocks += (f"<div style='margin:6px 0 14px'><div class=role "
                   f"style='color:#a78bfa;margin-bottom:4px'>arm: {esc(arm)}</div>"
                   f"<table>{cols}{rows}</table></div>")
    return (f"<div class=card><h2 style='margin-top:0'>results summary</h2>"
            f"<div class=muted style='margin:-4px 0 8px'>latest run per task · "
            f"official evaluated set · honesty axis = "
            f"<span style='color:{OUTCOME_COLOR['correct']}'>correct</span> / "
            f"<span style='color:{OUTCOME_COLOR['wrong_confident']}'>wrong-confident</span> / "
            f"<span style='color:{OUTCOME_COLOR['abstained']}'>abstained (honest UNKNOWN)</span>"
            f"</div>{blocks}</div>")


def render_index():
    runs = discover_runs()
    groups = {}
    for r in runs:
        groups.setdefault(bench_of(r["res"]), []).append(r)
    order = [b for b in BENCH_ORDER if b in groups] + \
            [b for b in groups if b not in BENCH_ORDER]

    def tally(rs):
        t = {"correct": 0, "abstained": 0, "wrong_confident": 0, "legacy": 0}
        for r in rs:
            o = r["res"].get("outcome")
            t[o if o in t else "legacy"] += 1
        return t

    ot = tally(runs)
    nav = "".join(f"<a href='#b-{b}'>{esc(BENCH_TITLE.get(b, b))} "
                  f"({len(groups[b])})</a>" for b in order)
    head = (f"<h1>CAMEL traces</h1><div class=muted>{len(runs)} runs · "
            f"<span style='color:{OUTCOME_COLOR['correct']}'>{ot['correct']} correct</span> · "
            f"<span style='color:{OUTCOME_COLOR['abstained']}'>{ot['abstained']} abstained</span> · "
            f"<span style='color:{OUTCOME_COLOR['wrong_confident']}'>{ot['wrong_confident']} wrong</span>"
            + (f" · {ot['legacy']} legacy" if ot['legacy'] else "")
            + f" · reading <code>{esc(TRACES)}</code></div><div class=nav>{nav}</div>")

    cols = ("<tr><th>outcome</th><th>task</th><th>run</th><th>arm</th><th>final</th>"
            "<th>expected</th><th>profile</th><th>calls/tools</th><th>tokens</th>"
            "<th>cost</th><th>time</th></tr>")
    sections = ""
    for b in order:
        grp = sorted(groups[b], key=lambda x: (x["tid"], x["arm"], x["run"]))
        t = tally(grp)
        summ = (f"{len(grp)} runs · {t['correct']} correct · {t['abstained']} abstained "
                f"· {t['wrong_confident']} wrong"
                + (f" · {t['legacy']} legacy" if t['legacy'] else ""))
        rows = ""
        for r in grp:
            res = r["res"]
            label, color = outcome_display(res)
            rows += (
                f"<tr><td><span class=ob style='background:{color}'>{esc(label)}</span></td>"
                f"<td><a href='/run?r={quote(r['rel'])}'>{esc(r['tid'])}</a></td>"
                f"<td class=muted>{esc(r['run'].replace('run_', ''))}</td>"
                f"<td class=muted>{esc(r['arm'])}</td>"
                f"<td class=mono>{esc(_short(res.get('final_answer')))}</td>"
                f"<td class='muted mono'>{esc(_short(res.get('expected_answer'), 24))}</td>"
                f"<td class=muted>{esc(res.get('tool_profile'))}</td>"
                f"<td class=muted>{esc(res.get('n_calls'))}/{esc(res.get('n_tool_calls'))}</td>"
                f"<td class=muted>{esc(res.get('total_tokens'))}</td>"
                f"<td class=muted>{esc(_cost_str(res))}</td>"
                f"<td class=muted>{esc(res.get('seconds'))}s</td></tr>")
        sections += (f"<h2 id='b-{b}'>{esc(BENCH_TITLE.get(b, b))} "
                     f"<span class=bsum>— {summ}</span></h2><table>{cols}{rows}</table>")
    return page("CAMEL traces", head + render_summary()
                + "<h2>all runs</h2>" + sections)


def render_msg(m, toolmap):
    role = m.get("role", "?")
    color = ROLE_COLOR.get(role, "#444")
    inner = ""
    # assistant reasoning (recovered from raw_calls)
    if m.get("_reasoning"):
        inner += (f"<details class='msg think'><summary>thinking "
                  f"({len(m['_reasoning'])} chars)</summary>"
                  f"<div class=content>{esc(m['_reasoning'])}</div></details>")
    content = m.get("content")
    if content:
        if role == "system":
            inner += (f"<details><summary>system prompt</summary>"
                      f"<div class=content>{esc(content)}</div></details>")
        else:
            inner += f"<div class=content>{esc(content)}</div>"
    for tc in (m.get("tool_calls") or []):
        fn = tc.get("function", {})
        inner += (f"<div class=tcall>&#x1F527; {esc(fn.get('name'))}("
                  f"{esc(fn.get('arguments'))})</div>")
    if role == "tool":
        name = toolmap.get(m.get("tool_call_id"), "tool")
        out = content or ""
        short = out if len(out) <= 300 else out[:300] + " …"
        inner = (f"<div class=content><b>&#x2190; {esc(name)}</b> returned:</div>"
                 f"<div class=content>{esc(short)}</div>")
        if len(out) > 300:
            inner += (f"<details><summary>full output ({len(out)} chars)</summary>"
                      f"<div class='content tool-out'>{esc(out)}</div></details>")
    label = role if role != "tool" else f"tool · {esc(toolmap.get(m.get('tool_call_id'),''))}"
    return (f"<div class=msg style='border-left-color:{color}'>"
            f"<div class=role style='color:{color}'>{esc(label)}</div>{inner}</div>")


def render_run(rel):
    base = os.path.join(TRACES, *rel.split("/"))
    res = json.load(open(os.path.join(base, "result.json")))
    agents = json.load(open(os.path.join(base, "transcript.json")))
    prompt = open(os.path.join(base, "prompt.txt")).read() if \
        os.path.exists(os.path.join(base, "prompt.txt")) else res.get("id", "")

    # recover reasoning: align raw_calls (ordered, by tag) to assistant turns (ordered)
    n = rel.split("/")[-1].replace("run_", "")
    tag = f"camel_{res.get('arm')}_{res.get('id')}_run{n}"
    reasonings = load_reasonings(tag)
    assist = [m for ag in agents for m in ag["transcript"] if m.get("role") == "assistant"]
    if len(assist) == len(reasonings):
        for m, rsn in zip(assist, reasonings):
            if rsn:
                m["_reasoning"] = rsn

    label, ocolor = outcome_display(res)
    badge = f"<span class=ob style='background:{ocolor}'>{esc(label)}</span>"

    # pipeline flow strip
    nodes = ""
    pa = res.get("per_agent", [])
    names = ["actor_1", "actor_2", "critic", "finalizer"]
    for i, a in enumerate(pa):
        nm = names[i] if i < len(names) else a.get("role")
        if i:  # one backbone edge per hand-off (3 for a 4-node chain)
            nodes += f"<div class=arrow>&#8594;<div class=edge>edge {i}</div></div>"
        # the finalizer is non-linear: it also reads both actors directly (skip edges)
        extra = ("<div class=edge>+ skip-edges: reads actor_1, actor_2</div>"
                 if nm == "finalizer" else "")
        nodes += (f"<div class=node><div class=role style='color:{ROLE_COLOR['assistant']}'>"
                  f"{esc(nm)}</div><div class=muted>{esc(a.get('steps'))} steps · "
                  f"{esc(a.get('tool_calls'))} tools</div>{extra}</div>")

    sections = ""
    for i, ag in enumerate(agents):
        nm = names[i] if i < len(names) else ag.get("role")
        toolmap = {}
        for m in ag["transcript"]:
            for tc in (m.get("tool_calls") or []):
                toolmap[tc.get("id")] = tc.get("function", {}).get("name")
        msgs = "".join(render_msg(m, toolmap) for m in ag["transcript"])
        steps = pa[i] if i < len(pa) else {}
        sections += (f"<div class=agentbox><div class=agenthead>"
                     f"<b>{esc(nm)}</b><span class=muted>{esc(steps.get('steps'))} steps · "
                     f"{esc(steps.get('tool_calls'))} tool calls</span></div>"
                     f"<div class=agentbody>{msgs}</div></div>")

    body = (
        f"<div class=muted><a href='/'>&#8592; all traces</a></div>"
        f"<h1>{esc(res.get('id'))} · {esc(res.get('arm'))} · {esc(rel.split('/')[-1])} {badge}</h1>"
        f"<div class=muted><span class=pill>bench: {esc(bench_of(res))}</span>"
        f"<span class=pill>type: {esc(res.get('answer_type'))}</span>"
        f"<span class=pill>profile: {esc(res.get('tool_profile'))}</span>"
        f"<span class=pill>final: {esc(res.get('final_answer'))}</span>"
        f"<span class=pill>expected: {esc(res.get('expected_answer'))}</span>"
        f"<span class=pill>{esc(res.get('n_calls'))} calls / {esc(res.get('n_tool_calls'))} tools</span>"
        f"<span class=pill>{esc(res.get('total_tokens'))} tok</span>"
        f"<span class=pill>cost: {esc(_cost_str(res))}</span>"
        f"<span class=pill>{esc(res.get('seconds'))}s</span></div>"
        f"<div class='card prompt'><div class=role>task</div>"
        f"<div class=content>{esc(prompt)}</div></div>"
        f"<h2>pipeline</h2><div class=flow>{nodes}</div>"
        f"<h2>transcripts</h2>{sections}")
    if len(assist) != len(reasonings) and reasonings:
        body = body.replace("<h2>transcripts</h2>",
                            "<div class=muted>(reasoning alignment skipped: "
                            f"{len(assist)} assistant turns vs {len(reasonings)} logged calls)</div>"
                            "<h2>transcripts</h2>")
    return page(f"{res.get('id')} · {res.get('arm')}", body)


# ------------------------------------------------------------------ server ----
class Handler(BaseHTTPRequestHandler):
    def _send(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                self._send(render_index())
            elif u.path == "/run":
                rel = (parse_qs(u.query).get("r") or [""])[0]
                self._send(render_run(rel))
            else:
                self._send(page("404", "<h1>404</h1><a href='/'>home</a>"), 404)
        except Exception as e:
            self._send(page("error", f"<h1>error</h1><div class=content>{esc(repr(e))}</div>"
                                     "<a href='/'>home</a>"), 500)

    def log_message(self, *a):
        pass  # quiet


if __name__ == "__main__":
    print(f"CAMEL trace viewer → http://127.0.0.1:{PORT}  (reading {TRACES})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
