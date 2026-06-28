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

ROLE_COLOR = {"system": "#6b7280", "user": "#2563eb",
              "assistant": "#059669", "tool": "#d97706"}

CSS = """
*{box-sizing:border-box} body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
margin:0;background:#0f1115;color:#e5e7eb} a{color:#60a5fa;text-decoration:none}
a:hover{text-decoration:underline} .wrap{max-width:1000px;margin:0 auto;padding:24px}
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
def render_index():
    runs = discover_runs()
    n_pass = sum(1 for r in runs if r["res"].get("exact_match"))
    rows = ""
    last_arm = None
    for r in sorted(runs, key=lambda x: (x["arm"], x["tid"], x["run"])):
        if r["arm"] != last_arm:
            rows += f"<tr><td colspan=8><h2>{esc(r['arm'])}</h2></td></tr>"
            last_arm = r["arm"]
        res = r["res"]
        ok = res.get("exact_match")
        badge = "<span class=pass>PASS</span>" if ok else "<span class=fail>FAIL</span>"
        rows += (
            f"<tr><td>{badge}</td>"
            f"<td><a href='/run?r={quote(r['rel'])}'>{esc(r['tid'])}</a></td>"
            f"<td class=muted>{esc(r['run'])}</td>"
            f"<td>{esc(res.get('final_answer'))}</td>"
            f"<td class=muted>{esc(res.get('expected_answer'))}</td>"
            f"<td>{esc(res.get('n_calls'))}/{esc(res.get('n_tool_calls'))}</td>"
            f"<td>{esc(res.get('total_tokens'))}</td>"
            f"<td class=muted>{esc(res.get('seconds'))}s</td></tr>")
    body = (f"<h1>CAMEL traces</h1><div class=muted>{len(runs)} runs · "
            f"{n_pass} pass · {len(runs)-n_pass} fail · reading <code>{esc(TRACES)}</code></div>"
            "<table><tr><th></th><th>task</th><th>run</th><th>final</th>"
            "<th>expected</th><th>calls/tools</th><th>tokens</th><th>time</th></tr>"
            f"{rows}</table>")
    return page("CAMEL traces", body)


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

    ok = res.get("exact_match")
    badge = ("<span class=pass>PASS</span>" if ok else "<span class=fail>FAIL</span>")

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
        f"<div class=muted><span class=pill>final: {esc(res.get('final_answer'))}</span>"
        f"<span class=pill>expected: {esc(res.get('expected_answer'))}</span>"
        f"<span class=pill>{esc(res.get('n_calls'))} calls / {esc(res.get('n_tool_calls'))} tools</span>"
        f"<span class=pill>{esc(res.get('total_tokens'))} tok</span>"
        f"<span class=pill>{esc(res.get('seconds'))}s</span>"
        f"<span class=pill>profile: {esc(res.get('tool_profile'))}</span></div>"
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
