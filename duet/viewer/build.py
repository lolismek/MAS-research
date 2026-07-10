"""Build the duet trace viewer: one self-contained HTML over duet/traces/**.

Walks every run dir, embeds result.json + transcript.json + the edge artifacts
(handoff notes / reports / plan / messages / belief store / judge) as JSON inside
a single-page app. Nothing is fetched at view time — open the file directly or
serve the folder.

Run:  python duet/viewer/build.py        ->  duet/viewer/index.html
"""
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TRACES = os.path.join(ROOT, "traces")
OUT = os.path.join(HERE, "index.html")

# --- architecture invariants (computed live off the stored message arrays) -----
# Markers are the EXACT delimiters the harness injects (harness/prompts.py). A check
# proves the geometry held in the actual run, not just in the offline prompt-diff audit.
_M_TASK = "<task>"
_M_NOTE = "<handoff_note>"
_M_ASSIGN = "<assignment>"
_M_REPORTS = "<worker_reports>"
_M_STORE = "<shared_record>"


def _leading_context(agent):
    """Messages before this agent's FIRST assistant turn = the context injected into it."""
    lead = []
    for m in agent.get("transcript", []):
        if m.get("role") == "assistant":
            break
        lead.append(m)
    return lead


def _txt(msgs):
    return "\n".join((m.get("content") or "") for m in msgs)


def _assignment_of(agent):
    m = re.search(r"<assignment>\n(.*?)\n</assignment>", _txt(_leading_context(agent)), re.S)
    return (m.group(1).strip() if m else "")


def _tool_outputs(agent):
    return [(m.get("content") or "") for m in agent.get("transcript", [])
            if m.get("role") == "tool"]


def invariants(result, agents, artifacts):
    """Return [{name, status: pass|fail|na, detail}] — the topology/arm hygiene rules
    checked against THIS run's transcripts. Conservative: only FAIL when certain."""
    topo, arm = result.get("topology"), result.get("arm")
    stats = result.get("arm_stats") or {}
    out = []

    def add(name, status, detail):
        out.append(dict(name=name, status=status, detail=detail))

    if topo == "hub":
        orchs = [a for a in agents if a.get("role") == "orchestrator"]
        workers = [a for a in agents if str(a.get("role", "")).startswith("worker_")]
        n_orch_tools = sum(len(m.get("tool_calls") or [])
                           for a in orchs for m in a.get("transcript", []))
        add("orchestrator is tool-less", "pass" if n_orch_tools == 0 else "fail",
            f"{n_orch_tools} tool call(s) by the orchestrator (must be 0 — it plans/merges only)")

        assigns = {a["role"]: _assignment_of(a) for a in workers}
        leaks = []
        for w in workers:
            body = _txt(w.get("transcript", []))
            own = assigns.get(w["role"], "")
            if _M_REPORTS in body:
                leaks.append(f"{w['role']} saw the merge's <worker_reports> layer")
            for other, sq in assigns.items():
                # only a real leak if the OTHER assignment is DISTINCT from this worker's
                # own — two workers handed the same subq (redundant plan) is not a leak.
                if other != w["role"] and sq and len(sq) > 20 and sq != own and sq[:80] in body:
                    leaks.append(f"{w['role']} saw {other}'s distinct assignment")
        if workers:
            add("worker blindness (spatial asymmetry)", "pass" if not leaks else "fail",
                "; ".join(leaks) or f"each of {len(workers)} worker(s) saw only its own <assignment>")
        else:
            add("worker blindness (spatial asymmetry)", "na", "no workers recorded")

        # plan quality (not a hygiene violation): flag redundant/duplicate sub-questions
        vals = [v for v in assigns.values() if v]
        dups = len(vals) - len(set(vals))
        if dups:
            add("orchestrator plan is non-redundant", "warn",
                f"{dups} duplicate sub-question(s) — the decompose spawned redundant workers")

    if topo == "relay":
        shifts = list(agents)
        if len(shifts) < 2:
            add("relay context reset (temporal asymmetry)", "na",
                "single shift — no edge crossed")
        else:
            leaked = []
            for k in range(1, len(shifts)):
                lead = _txt(_leading_context(shifts[k]))
                for to in _tool_outputs(shifts[k - 1]):
                    probe = to[120:320]
                    if len(probe) > 100 and probe in lead:
                        leaked.append(f"shift_{k + 1} context carried shift_{k}'s raw tool output")
                        break
            if arm == "full":
                add("relay full arm carries prior transcript", "pass" if leaked else "na",
                    "successor received the predecessor's raw log via <shared_record>"
                    if leaked else "no verbatim carry detected (short predecessor)")
            else:
                add("relay context reset (temporal asymmetry)", "pass" if not leaked else "fail",
                    "; ".join(leaked) or "successors got a fresh context — only the hand-off note crossed")

    # store rendering, arm-specific
    any_store = any(_M_STORE in _txt(a.get("transcript", [])) for a in agents)
    if arm == "board_inert":
        add("board_inert never renders the store", "pass" if not any_store else "fail",
            "store block leaked into a context (must never render)" if any_store
            else "<shared_record> absent everywhere, as designed")
    elif arm in ("board", "extract"):
        wrote = stats.get("beliefs_added", 0) + stats.get("beliefs_extracted", 0)
        if wrote:
            add("belief store is rendered to successors", "pass" if any_store else "fail",
                f"{wrote} belief(s) written; <shared_record> "
                + ("shown downstream" if any_store else "NOT shown — write/read seam broken"))
        else:
            add("belief store rendered", "na", "no beliefs written this run (short task)")
    elif arm == "full":
        if stats.get("transcripts_stored", 0):
            add("full arm renders prior transcript", "pass" if any_store else "fail",
                "<shared_record> " + ("shown downstream" if any_store else "missing despite stored transcript"))
    elif arm == "down":
        asks = stats.get("down_edges", 0)
        fired = stats.get("down_challenges", 0)
        declined = stats.get("down_declines")
        if not asks:
            add("down consumer challenge", "na", "no eligible edges this run")
        elif fired:
            add("down consumer challenge", "pass",
                f"{fired} challenge(s) fired on {asks} ask(s)"
                + (f", {declined} declined" if declined else "")
                + " — Q/A visible in the edge payloads")
        else:
            add("down consumer challenge", "na",
                f"0 challenges on {asks} ask(s) — consumer declined every time"
                + (" (see challenges.txt)" if declined is not None else
                   " (pre-instrumentation run: declines not logged)"))

    if topo == "dialogue":
        peers = [a for a in agents if str(a.get("role", "")).startswith("peer_")]
        add("dialogue has ≥2 persistent peers", "pass" if len(peers) >= 2 else "na",
            f"{len(peers)} peer(s): " + ", ".join(a.get("role", "?") for a in peers))

    # universal: no context layer bleeds into the wrong topology
    if agents and any(_M_TASK in _txt(_leading_context(a)) for a in agents):
        add("task delimited in every agent context", "pass", "<task>…</task> present")
    return out

_ARTIFACTS = {
    "notes": "handoff_notes.txt", "reports": "reports.txt", "plan": "plan.txt",
    "messages": "messages.txt", "challenges": "challenges.txt", "prompt": "prompt.txt",
}
_JSON_ARTIFACTS = {"store": "store.json", "judge": "judge.json"}


def _read(p):
    try:
        return open(p, encoding="utf-8").read()
    except OSError:
        return None


def collect():
    runs = []
    for root, _dirs, files in os.walk(TRACES):
        if "result.json" not in files:
            continue
        r = json.loads(_read(os.path.join(root, "result.json")))
        agents = []
        t = _read(os.path.join(root, "transcript.json"))
        if t:
            try:
                agents = json.loads(t)
            except ValueError:
                agents = []
        art = {}
        for key, fn in _ARTIFACTS.items():
            v = _read(os.path.join(root, fn))
            if v:
                art[key] = v
        for key, fn in _JSON_ARTIFACTS.items():
            v = _read(os.path.join(root, fn))
            if v:
                try:
                    art[key] = json.dumps(json.loads(v), indent=1)
                except ValueError:
                    art[key] = v
        has_cot = any(m.get("reasoning_content")
                      for a in agents if isinstance(a, dict)
                      for m in a.get("transcript", []) if isinstance(m, dict))
        checks = invariants(r, agents, art)
        mtime = os.path.getmtime(os.path.join(root, "result.json"))
        runs.append(dict(
            dir=os.path.relpath(root, TRACES), result=r, agents=agents,
            artifacts=art, has_cot=has_cot, checks=checks,
            n_fail=sum(1 for c in checks if c["status"] == "fail"),
            mtime=mtime,
            # batch = the run's calendar day (from result.json mtime). The list view
            # splits the NEWEST batch into its own region so a fresh sweep is
            # reviewable in isolation; self-maintaining across rebuilds.
            batch=time.strftime("%Y-%m-%d", time.localtime(mtime))))
    runs.sort(key=lambda x: (x["result"].get("topology") or "", x["result"].get("arm") or "",
                             x["result"].get("bench") or "", x["result"].get("id") or "",
                             x["dir"]))
    return runs


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>duet trace viewer</title>
<style>
:root{--bg:#12141a;--panel:#1a1e27;--panel2:#20242f;--fg:#d6dae3;--dim:#8891a0;--line:#2c3140;
 --sys:#9d7bd8;--usr:#5b9dd9;--asst:#5fbf77;--tool:#8891a0;--think:#d9a441;--bad:#e06c75;--good:#5fbf77;--warn:#d9a441;}
*{box-sizing:border-box}
body{margin:0;font:13px/1.5 -apple-system,"SF Mono",Menlo,monospace;background:var(--bg);color:var(--fg);display:flex;height:100vh;overflow:hidden}
#side{width:340px;min-width:340px;border-right:1px solid var(--line);display:flex;flex-direction:column}
#side header{padding:10px 12px;border-bottom:1px solid var(--line)}
#side h1{font-size:14px;margin:0 0 8px}
#side select,#side input{background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:4px;padding:3px 6px;font:inherit;margin:0 4px 4px 0}
#runs{flex:1;overflow-y:auto}
.grp{padding:6px 12px 2px;color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.06em;position:sticky;top:0;background:var(--bg)}
.region{position:static;margin-top:6px;padding:7px 12px 5px;font-weight:700;color:var(--fg);background:var(--panel);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.region.new{color:var(--think);border-top-color:var(--think)}
.run{padding:5px 12px;cursor:pointer;display:flex;gap:8px;align-items:center;border-left:3px solid transparent}
.run:hover{background:var(--panel)} .run.sel{background:var(--panel2);border-left-color:var(--usr)}
.dot{width:9px;height:9px;border-radius:50%;flex:none}
.dot.correct{background:var(--good)} .dot.wrong_confident{background:var(--bad)}
.dot.abstained{background:var(--warn)} .dot.no_answer{background:#777}
.run .id{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.run .meta{color:var(--dim);font-size:11px;flex:none}
.cot{color:var(--think);font-size:11px}
#main{flex:1;overflow-y:auto;padding:16px 22px}
.badge{display:inline-block;padding:1px 8px;border-radius:9px;font-size:11px;border:1px solid var(--line);background:var(--panel);margin-right:6px}
.badge.correct{color:var(--good);border-color:var(--good)} .badge.wrong_confident{color:var(--bad);border-color:var(--bad)}
.badge.abstained{color:var(--warn);border-color:var(--warn)} .badge.no_answer{color:var(--dim)}
h2{font-size:15px;margin:0 0 6px} h3{font-size:13px;margin:18px 0 6px;color:var(--dim)}
table.kv{border-collapse:collapse;margin:8px 0}
table.kv td{padding:1px 14px 1px 0;color:var(--dim)} table.kv td:nth-child(2n){color:var(--fg)}
.answer{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 10px;margin:6px 0;white-space:pre-wrap}
details{margin:4px 0;border:1px solid var(--line);border-radius:6px;background:var(--panel)}
details>summary{cursor:pointer;padding:5px 10px;color:var(--dim);user-select:none}
details[open]>summary{border-bottom:1px solid var(--line)}
details>.body{padding:8px 10px;white-space:pre-wrap;overflow-x:auto;max-height:480px;overflow-y:auto}
.agent{border:1px solid var(--line);border-radius:8px;margin:10px 0;background:var(--panel)}
.agent>.head{padding:6px 12px;border-bottom:1px solid var(--line);cursor:pointer;display:flex;gap:10px;align-items:center}
.agent>.head .role{font-weight:700}
.agent>.head .fin{color:var(--dim);font-size:11px}
.msgs{padding:8px 12px;display:none} .agent.open .msgs{display:block}
.msg{margin:8px 0;border-left:3px solid var(--line);padding:2px 0 2px 10px}
.msg .who{font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px}
.msg.system{border-left-color:var(--sys)} .msg.system .who{color:var(--sys)}
.msg.user{border-left-color:var(--usr)} .msg.user .who{color:var(--usr)}
.msg.assistant{border-left-color:var(--asst)} .msg.assistant .who{color:var(--asst)}
.msg.tool{border-left-color:var(--tool)} .msg.tool .who{color:var(--tool)}
.msg .txt{white-space:pre-wrap;overflow-wrap:anywhere}
.think{border:1px dashed var(--think);border-radius:6px;margin:4px 0;background:rgba(217,164,65,.06)}
.think>summary{color:var(--think);padding:3px 8px;cursor:pointer}
.think>.body{padding:6px 10px;white-space:pre-wrap;color:#cbb27a;max-height:400px;overflow-y:auto}
.tc{border:1px solid var(--asst);border-radius:6px;margin:4px 0;background:rgba(95,191,119,.05)}
.tc>summary{color:var(--asst);padding:3px 8px;cursor:pointer}
.tc>.body{padding:6px 10px;white-space:pre-wrap;overflow-x:auto}
.toolout{max-height:260px;overflow-y:auto}
mark{background:rgba(91,157,217,.25);color:inherit;border-radius:3px;padding:0 2px}
mark.final{background:rgba(95,191,119,.3);font-weight:700}
mark.inject{background:rgba(157,123,216,.25)}
mark.trunc{background:rgba(224,108,117,.3)}
.pill{font-size:11px;color:var(--dim)}
.checks{border:1px solid var(--line);border-radius:8px;margin:10px 0;background:var(--panel)}
.checks>.hd{padding:6px 12px;border-bottom:1px solid var(--line);font-weight:700;display:flex;gap:8px;align-items:center}
.chk{display:flex;gap:9px;align-items:baseline;padding:4px 12px;border-top:1px solid rgba(44,49,64,.5)}
.chk:first-of-type{border-top:0}
.chk .st{font-size:11px;font-weight:700;padding:0 6px;border-radius:9px;flex:none;min-width:38px;text-align:center}
.chk.pass .st{color:var(--good);border:1px solid var(--good)}
.chk.fail .st{color:var(--bad);border:1px solid var(--bad);background:rgba(224,108,117,.12)}
.chk.na .st{color:var(--dim);border:1px solid var(--line)}
.chk.warn .st{color:var(--warn);border:1px solid var(--warn);background:rgba(217,164,65,.12)}
.chk .nm{font-weight:600;flex:none} .chk .dt{color:var(--dim)}
.chk.fail .nm{color:var(--bad)} .chk.warn .nm{color:var(--warn)}
.run .fail{color:var(--bad);font-weight:700;font-size:11px;flex:none}
#empty{color:var(--dim);margin-top:40vh;text-align:center}
</style></head><body>
<div id="side">
 <header>
  <h1>duet trace viewer <span class="pill" id="count"></span></h1>
  <div>
   <select id="f_topo"><option value="">topology</option></select>
   <select id="f_arm"><option value="">arm</option></select>
   <select id="f_bench"><option value="">bench</option></select>
  </div>
  <div>
   <select id="f_out"><option value="">outcome</option></select>
   <label class="pill"><input type="checkbox" id="f_cot"> 💭 thinking</label>
   <label class="pill"><input type="checkbox" id="f_fail"> ✗ failing check</label>
   <label class="pill"><input type="checkbox" id="f_new"> 🆕 new batch only</label>
  </div>
  <input id="f_q" placeholder="filter by task id…" style="width:97%">
 </header>
 <div id="runs"></div>
</div>
<div id="main"><div id="empty">select a run</div></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const RUNS = JSON.parse(document.getElementById('data').textContent);
const $ = s => document.querySelector(s);
const esc = s => (s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

// sentinel + hygiene highlighting (applied to escaped text)
const SENT = /^(FINAL ANSWER:|SUBQ:|FINDINGS:|VERDICT:|CONFIDENCE:|EVIDENCE:|NEXT_STEPS:|BELIEF:|DECISION:|QUESTION:|FOLLOWUP:|NOTE:)/gm;
function hl(s){
  let h = esc(s);
  h = h.replace(/^FINAL ANSWER:.*$/gm, m=>`<mark class="final">${m}</mark>`);
  h = h.replace(SENT, m=>`<mark>${m}</mark>`);
  h = h.replace(/&lt;(\/?)(task|assignment|shared_record)&gt;/g, (m)=>`<mark class="inject">${m}</mark>`);
  h = h.replace(/\[(clarifying question from the worker taking over|answer from the note's author|pre-merge clarifying question about this report|answer from the report's author)\]/g,
                m=>`<mark class="inject">${m}</mark>`);
  h = h.replace(/^(DECLINED|SKIPPED)( — .*)$/gm, m=>`<mark class="trunc">${m}</mark>`);
  h = h.replace(/\[(the model could not finish[^\]]*|truncated[^\]]*|note truncated[^\]]*|no note survived[^\]]*)\]/g,
                m=>`<mark class="trunc">${m}</mark>`);
  return h;
}
const uniq = k => [...new Set(RUNS.map(r=>r.result[k]).filter(Boolean))].sort();
for (const [id,k] of [['#f_topo','topology'],['#f_arm','arm'],['#f_bench','bench'],['#f_out','outcome']])
  uniq(k).forEach(v=>{const o=document.createElement('option');o.value=o.textContent=v;$(id).appendChild(o);});

let sel = null;
const NEWEST = RUNS.reduce((m,r)=>r.batch>m?r.batch:m,'');
function renderList(){
  const t=$('#f_topo').value, a=$('#f_arm').value, b=$('#f_bench').value,
        o=$('#f_out').value, q=$('#f_q').value.toLowerCase(), c=$('#f_cot').checked,
        fl=$('#f_fail').checked, nw=$('#f_new').checked;
  const box=$('#runs'); box.innerHTML='';
  const keep = r => {
    const R=r.result;
    if((t&&R.topology!==t)||(a&&R.arm!==a)||(b&&R.bench!==b)||(o&&R.outcome!==o)) return false;
    if(q&&!R.id.toLowerCase().includes(q)) return false;
    if(c&&!r.has_cot) return false;
    if(fl&&!r.n_fail) return false;
    return true;
  };
  const region = (rows, label, cls) => {           // rows = [origIndex, run]
    if(!rows.length) return;
    const h=document.createElement('div'); h.className='grp region'+(cls?' '+cls:'');
    h.textContent=label; box.appendChild(h);
    let last='';
    for(const [i,r] of rows){
      const R=r.result, g=`${R.topology} · ${R.arm}`;
      if(g!==last){const d=document.createElement('div');d.className='grp';d.textContent=g;box.appendChild(d);last=g;}
      const d=document.createElement('div');
      d.className='run'+(i===sel?' sel':''); d.dataset.i=i;
      d.innerHTML=`<span class="dot ${R.outcome}"></span><span class="id">${esc(R.id)}<span class="pill"> ${esc(r.dir.split('/').pop())}</span></span>`+
        (r.n_fail?`<span class="fail">✗${r.n_fail}</span>`:'')+
        (r.has_cot?'<span class="cot">💭</span>':'')+
        `<span class="meta">$${(R.cost_usd||0).toFixed(3)}</span>`;
      d.onclick=()=>{sel=i;renderList();renderRun(r);};
      box.appendChild(d);
    }
  };
  const kept = RUNS.map((r,i)=>[i,r]).filter(([,r])=>keep(r));
  const fresh = kept.filter(([,r])=>r.batch===NEWEST);
  const older = kept.filter(([,r])=>r.batch!==NEWEST);
  region(fresh, `🆕 newest batch — ${NEWEST} (${fresh.length})`, 'new');
  if(!nw) region(older, `earlier runs (${older.length})`);
  const n = fresh.length + (nw?0:older.length);
  $('#count').textContent = `${n}/${RUNS.length}`;
}
function kv(rows){
  return '<table class="kv">'+rows.filter(r=>r[1]!==undefined&&r[1]!==null&&r[1]!=='')
    .map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('')+'</table>';
}
function det(title, body, cls='', open=false){
  return `<details ${open?'open':''} class="${cls}"><summary>${title}</summary><div class="body">${body}</div></details>`;
}
function renderMsg(m){
  let out = `<div class="msg ${m.role}"><div class="who">${m.role}</div>`;
  if(m.reasoning_content)
    out += `<details class="think"><summary>💭 thinking (${m.reasoning_content.length} chars)</summary><div class="body">${esc(m.reasoning_content)}</div></details>`;
  const c = m.content;
  if(c){
    if(m.role==='tool')
      out += det(`tool result (${c.length} chars)`, `<div class="toolout">${hl(c)}</div>`, '', c.length<600);
    else if(m.role==='system')
      out += det(`system prompt (${c.length} chars)`, hl(c), '', false);
    else
      out += `<div class="txt">${hl(c)}</div>`;
  }
  for(const tc of (m.tool_calls||[])){
    const f=tc.function||{};
    let args=f.arguments||'';
    try{args=JSON.stringify(JSON.parse(args),null,1);}catch(e){}
    out += `<details class="tc" ${args.length<400?'open':''}><summary>🔧 ${esc(f.name)}</summary><div class="body">${esc(args)}</div></details>`;
  }
  return out+'</div>';
}
function renderRun(r){
  const R=r.result, m=$('#main');
  const extra=[];
  if(R.topology==='relay') extra.push(['shifts used',R.shifts_used],['k',R.k]);
  if(R.topology==='hub') extra.push(['subqs',R.n_subqs],['degenerate plan',R.degenerate_plan],['followup',R.followup_used]);
  if(R.topology==='dialogue') extra.push(['turns',R.turns_used],['proposals',R.proposals],['contests',R.contests],['ratified',R.ratified]);
  let h = `<h2><span class="badge ${R.outcome}">${R.outcome}</span>
    <span class="badge">${R.topology}</span><span class="badge">${R.arm}</span>
    <span class="badge">${R.bench}</span> ${esc(R.id)} <span class="pill">${esc(r.dir)}</span></h2>`;
  h += `<div class="answer"><b>final:</b> ${hl(R.final_answer||'—')}\n<b>expected:</b> ${esc(String(R.expected_answer))}</div>`;
  if((r.checks||[]).length){
    const nf=r.n_fail, np=r.checks.filter(c=>c.status==='pass').length,
          nw=r.checks.filter(c=>c.status==='warn').length;
    h += `<div class="checks"><div class="hd">🏗 architecture invariants
      <span class="pill">${np} pass${nf?` · <span style="color:var(--bad)">${nf} fail</span>`:''}`+
      `${nw?` · <span style="color:var(--warn)">${nw} warn</span>`:''}</span></div>`;
    for(const c of r.checks)
      h += `<div class="chk ${c.status}"><span class="st">${c.status.toUpperCase()}</span>
        <span class="nm">${esc(c.name)}</span><span class="dt">${esc(c.detail)}</span></div>`;
    h += `</div>`;
  }
  h += kv([['finish',R.finish],['committed',R.committed],['budget exceeded',R.budget_exceeded],
     ...extra,['tool budget',R.tool_budget],['tool calls',R.n_tool_calls],['LLM calls',R.n_calls],
     ['edges',R.edges],['edge markers',R.edge_markers],['note yield',R.note_yield],
     ['arm stats',R.arm_stats?esc(JSON.stringify(R.arm_stats)):null],
     ['tokens',`${R.prompt_tokens} in / ${R.completion_tokens} out`],
     ['cost',`$${(R.cost_usd||0).toFixed(4)}`],['seconds',R.seconds],['proxy errors',R.proxy_errors]]);
  const A={notes:'hand-off notes (edge payloads)',plan:'orchestrator plan',reports:'worker reports (edge payloads)',
           messages:'peer messages (edge payloads)',challenges:'down ask outcomes (one per eligible edge)',
           store:'shared store (belief ledger)',judge:'process judge',prompt:'task prompt'};
  const artKeys=Object.keys(A).filter(k=>r.artifacts[k]);
  if(artKeys.length){
    h+='<h3>edge artifacts & shared state</h3>';
    for(const k of artKeys) h+=det(A[k], hl(r.artifacts[k]), '', k==='notes'||k==='reports'||k==='messages'||k==='challenges');
  }
  h+=`<h3>agent transcripts (${r.agents.length})</h3>`;
  r.agents.forEach((a,i)=>{
    const n=(a.transcript||[]).length;
    const cot=(a.transcript||[]).some(x=>x.reasoning_content);
    h+=`<div class="agent" id="ag${i}"><div class="head" onclick="this.parentNode.classList.toggle('open')">
      <span class="role">${esc(a.role)}</span><span class="fin">finish=${esc(a.finish||'?')} · ${n} messages</span>${cot?'<span class="cot">💭 has thinking</span>':''}</div>
      <div class="msgs">${(a.transcript||[]).map(renderMsg).join('')}</div></div>`;
  });
  m.innerHTML=h;
  if(r.agents.length===1) m.querySelector('.agent')?.classList.add('open');
  m.scrollTop=0;
}
['#f_topo','#f_arm','#f_bench','#f_out'].forEach(s=>$(s).onchange=renderList);
$('#f_q').oninput=renderList; $('#f_cot').onchange=renderList; $('#f_fail').onchange=renderList;
$('#f_new').onchange=renderList;
renderList();
</script></body></html>"""


def main():
    runs = collect()
    data = json.dumps(runs, ensure_ascii=False).replace("</", "<\\/")
    out = TEMPLATE.replace("__DATA__", data)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    n_cot = sum(1 for r in runs if r["has_cot"])
    size = os.path.getsize(OUT) / 1e6
    print(f"wrote {OUT}: {len(runs)} runs ({n_cot} with thinking), {size:.1f} MB")


if __name__ == "__main__":
    main()
