"""The relay: N agents, same model and prompt, K tool calls each, only the handoff text crosses.

run_relay(task, N, K, chat, corpus, incoming=None, start_agent=1, prefix_agents=None)
  -> dict trace. Agents start_agent..N are executed; agents before that are taken from
     prefix_agents (used for resume/injection: the suffix is resampled from agent i with a
     given incoming message).

Per agent (index i, 1-based):
  messages = [system(rules + tools), user(question + role line + incoming message)]
  loop: chat -> parse XML tool call
     finish(answer)     -> relay ends
     search/open        -> execute, append assistant raw text + user <tool_response> with budget line
     no tool call       -> nudge (max NUDGES), then treated as budget spent
  budget spent:
     i < N  -> ask for the handoff message (free-form); its reply is the handoff
     i == N -> ask for finish; one re-ask; else fall back to a FINAL ANSWER line / last text
"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from llm import tools_to_prompt
from tools import TOOL_SPECS, render

NUDGES = 2

RULES = """You are one agent in a relay of {N} agents solving a single question. Each agent works alone with a
fresh context, has a budget of {K} tool calls, and then hands a written message to the next agent. The next
agent sees ONLY the question and your message. Any agent may submit the final answer with finish() as soon as
it is confident.

Rules:
- Use only information obtained through the tools in this relay. Do not answer from memory or guess.
- Respect any date qualifier in the question (e.g. "as of August 2024").
- Call exactly one tool per turn, and nothing else in that turn.
- When you are confident of the answer, call finish(answer) with one short answer. finish() does not count
  against your tool budget; you may still call it after your last search/open.

{TOOLS}"""

BRIEFING_RULE = ("- Use only information obtained through the tools in this relay or stated in your briefing (if you have one). "
                 "Do not answer from memory or guess.")
BRIEFING = "\n\n# Briefing\n{B}"

def system_prompt(N, K, briefing=None, briefing_mode=False):
    """briefing_mode: internal-belief experiment (rule line admits a briefing; same wording for every agent in every arm).
    briefing: this agent's private briefing text (None = this agent holds nothing)."""
    s = RULES.format(N=N, K=K, TOOLS=tools_to_prompt(TOOL_SPECS))
    if briefing_mode or briefing:
        s = s.replace("- Use only information obtained through the tools in this relay. Do not answer from memory or guess.", BRIEFING_RULE)
    if briefing:
        s += BRIEFING.format(B=briefing.strip())
    return s

def user_prompt(question, i, N, K, incoming):
    s = f"Question: {question}\n\nYou are agent {i} of {N}. You have {K} tool calls."
    if incoming is None:
        s += "\n\nYou are the first agent; there is no incoming message."
    elif not incoming.strip():
        s += f"\n\nAgent {i-1} sent an empty message."
    else:
        s += f"\n\nMessage from agent {i-1}:\n<<<\n{incoming}\n>>>"
    return s

HANDOFF_PROMPT = ("Your tool budget is spent. If you are confident of the final answer, call finish(answer) now. "
                  "Otherwise write the message to the next agent: they start with a fresh context and will see only the "
                  "question and your message, so write whatever you think they need to finish the task, in whatever form "
                  "you think best. Plain text only; search and open are disabled.")
FINAL_PROMPT = ("Your tool budget is spent and you are the last agent. search and open are disabled now and any such call "
                "is ignored. You must now call finish(answer) with your best answer to the question.")
FINAL_REASK = "search/open are disabled. Call finish(answer) now: emit only the finish <tool_call> block."
NUDGE = "You did not call a tool. Call exactly one tool now (search, open, or finish). Calls remaining: {r}."
CUTOFF_REASK = "Your message was cut off before it was written out. Write the complete message now, concisely, without further deliberation."
BAD_FINISH_REASK = ("finish(answer) must contain only a short answer to the question (a name, number, date, word or short list), "
                    "not a message or explanation. If you have the answer, call finish with just the answer; otherwise keep working.")
_BAD_FINISH = re.compile(r"next agent|agent \d|I (found|could not|couldn't|need)|please", re.I)
def valid_finish(ans):
    return bool(ans) and len(ans) <= 200 and len(ans.split()) <= 25 and not _BAD_FINISH.search(ans)
NOTOOL_REASK = "That was not a message. Tools are disabled now. Write the message to the next agent in plain text."

_ANS = re.compile(r"^\W*(?:final\s+answer|answer)\W*:\s*(.+?)\W*$", re.I)
_PSEUDO = re.compile(r"^\s*(search|open|finish)\s*\(", re.I)
def _bad_handoff(h):
    """Empty, an XML tool call, or a bare pseudo-call like `search(query: ...)`."""
    return (not h) or ("<tool_call>" in h) or ("<function=" in h) or (_PSEUDO.match(h) and len(h) < 200)

def _strip_delims(t):
    """Drop a copied <<< ... >>> wrapper around a handoff."""
    t = t.strip()
    if t.startswith("<<<"): t = t[3:].strip()
    if t.endswith(">>>"): t = t[:-3].strip()
    return t

def _final_from_text(text):
    """Last 'FINAL ANSWER: x' / 'Answer: x' line, if any."""
    for line in reversed((text or "").splitlines()):
        m = _ANS.match(line.strip())
        if m and m.group(1).strip(): return m.group(1).strip().strip("*").strip()
    return None

def run_agent(i, N, K, question, incoming, chat, corpus, tag, briefing=None, briefing_mode=False):
    """Execute one agent. Returns dict(handoff, final, steps, messages, ...)."""
    msgs = [{"role": "system", "content": system_prompt(N, K, briefing=briefing, briefing_mode=briefing_mode)},
            {"role": "user", "content": user_prompt(question, i, N, K, incoming)}]
    steps, used, nudges, final, handoff, seen, handoff_invalid, bad_finishes = [], 0, 0, None, None, set(), False, 0
    cost = tokens_in = tokens_out = 0
    t0 = time.time()

    def call(tag_suffix):
        nonlocal cost, tokens_in, tokens_out
        r = chat.chat(msgs, tag=f"{tag}/a{i}/{tag_suffix}")
        cost += r["cost"]; tokens_in += r["prompt_tokens"]; tokens_out += r["completion_tokens"]
        return r

    while True:
        r = call(f"s{len(steps)}")
        step = dict(kind="turn", reasoning=r["reasoning"], text=r["content"], raw=r["raw_content"],
                    tool_calls=r["tool_calls"], finish_reason=r["finish"])
        steps.append(step)
        tc = r["tool_calls"][0] if r["tool_calls"] else None
        if tc and tc["name"] == "finish":
            ans = (tc["args"].get("answer") or "").strip()
            if valid_finish(ans) or bad_finishes >= 1:
                final = ans; step["result"] = f"finish({final!r})"
                break
            bad_finishes += 1; step["invalid_finish"] = True
            msgs.append({"role": "assistant", "content": r["raw_content"]})
            msgs.append({"role": "user", "content": BAD_FINISH_REASK})
            continue
        if tc and tc["name"] in ("search", "open"):
            used += 1
            args = dict(tc["args"])
            need = "query" if tc["name"] == "search" else "title"
            for k in list(args):                                                   # template placeholder copied verbatim
                if k.upper() == "ARG" and need not in args: args[need] = args.pop(k)
            if not (args.get(need) or "").strip():
                res = dict(error=f"missing parameter '{need}'"); obs = f"error: missing parameter '{need}' — {tc['name']} needs <parameter={need}>...</parameter>"
            else:
                res = corpus.search(args["query"]) if tc["name"] == "search" else corpus.open(args["title"], args.get("page", 1))
                obs = render(tc["name"], res)
            sig = (tc["name"], json.dumps(tc["args"], sort_keys=True))
            if sig in seen: obs += "\n(note: this call is identical to an earlier one in this session; the result is the same)"
            seen.add(sig)
            step["result"] = res; step["observation"] = obs
            msgs.append({"role": "assistant", "content": r["raw_content"]})
            remaining = K - used
            msgs.append({"role": "user", "content": f"<tool_response>\n{obs}\n</tool_response>\n(tool calls remaining: {remaining})"})
        else:
            # text only (or unknown tool): nudge, then treat as spent
            msgs.append({"role": "assistant", "content": r["raw_content"] or "(empty)"})
            nudges += 1
            if nudges <= NUDGES and used < K:
                msgs.append({"role": "user", "content": NUDGE.format(r=K - used)})
                continue
            used = K
        if used >= K:
            break

    if final is None:
        if i < N:
            msgs.append({"role": "user", "content": HANDOFF_PROMPT})
            r = call("handoff")
            tcf = r["tool_calls"][0] if r["tool_calls"] else None
            if tcf and tcf["name"] == "finish":
                ans = (tcf["args"].get("answer") or "").strip()
                if valid_finish(ans):
                    final = ans
                    steps.append(dict(kind="turn", reasoning=r["reasoning"], text=r["content"], raw=r["raw_content"],
                                      tool_calls=r["tool_calls"], finish_reason=r["finish"], result=f"finish({final!r})"))
                    msgs.append({"role": "assistant", "content": r["raw_content"]})
                    return _agent_record(i, incoming, None, handoff_invalid, final, used, nudges, steps, msgs, cost, tokens_in, tokens_out, t0, briefing)
                r["content"] = ans                      # a message stuffed into finish(): use it as the message
            handoff = _strip_delims((r["content"] or "").strip())
            steps.append(dict(kind="handoff", reasoning=r["reasoning"], text=handoff, finish_reason=r["finish"]))
            msgs.append({"role": "assistant", "content": r["raw_content"] or "(empty)"})
            bad = _bad_handoff(handoff)
            if r["finish"] == "length" or bad:   # thinking ate the output budget, or the reply was empty / a tool call
                msgs.append({"role": "user", "content": CUTOFF_REASK if r["finish"] == "length" else NOTOOL_REASK})
                r = call("handoff_retry")
                steps.append(dict(kind="handoff", reasoning=r["reasoning"], text=(r["content"] or "").strip(), finish_reason=r["finish"], retry=True))
                msgs.append({"role": "assistant", "content": r["raw_content"] or "(empty)"})
                if (r["content"] or "").strip():
                    handoff = _strip_delims(r["content"].strip())
            if _bad_handoff(handoff):
                handoff, handoff_invalid = "", True      # recorded as an empty message; the next agent is told so
        else:
            msgs.append({"role": "user", "content": FINAL_PROMPT})
            for attempt in range(2):
                r = call(f"final{attempt}")
                steps.append(dict(kind="final", reasoning=r["reasoning"], text=r["content"], raw=r["raw_content"],
                                  tool_calls=r["tool_calls"], finish_reason=r["finish"]))
                msgs.append({"role": "assistant", "content": r["raw_content"]})
                tc = r["tool_calls"][0] if r["tool_calls"] else None
                if tc and tc["name"] == "finish":
                    ans = (tc["args"].get("answer") or "").strip()
                    if valid_finish(ans) or attempt == 1: final = ans; break
                    steps[-1]["invalid_finish"] = True
                    msgs.append({"role": "user", "content": BAD_FINISH_REASK}); continue
                fa = _final_from_text(r["content"])
                if fa: final = fa; break
                msgs.append({"role": "user", "content": FINAL_REASK})
            if final is None:                      # last non-empty line of the last reply
                lines = [l.strip() for l in (steps[-1]["text"] or "").splitlines() if l.strip()]
                final = (lines[-1] if lines else "")[:300]
                steps[-1]["fallback"] = True
    return _agent_record(i, incoming, handoff, handoff_invalid, final, used, nudges, steps, msgs, cost, tokens_in, tokens_out, t0, briefing)

def _agent_record(i, incoming, handoff, handoff_invalid, final, used, nudges, steps, msgs, cost, tokens_in, tokens_out, t0, briefing=None):
    return dict(agent=i, incoming=incoming, handoff=handoff, handoff_invalid=handoff_invalid, final=final, tool_calls_used=used, nudges=nudges,
                briefing=briefing,
                steps=steps, messages=msgs, cost=cost, tokens_in=tokens_in, tokens_out=tokens_out,
                seconds=round(time.time() - t0, 1),
                opened=[s["result"]["title"] for s in steps if s.get("kind") == "turn" and s.get("tool_calls")
                        and s["tool_calls"][0]["name"] == "open" and isinstance(s.get("result"), dict) and "title" in s["result"]],
                searches=[s["tool_calls"][0]["args"].get("query", "") for s in steps if s.get("kind") == "turn"
                          and s.get("tool_calls") and s["tool_calls"][0]["name"] == "search"])

def run_relay(task, N, K, chat, corpus, tag, incoming=None, start_agent=1, prefix_agents=None, briefing=None, holders=()):
    """briefing/holders: internal-belief experiment. Agents whose index is in `holders` get `briefing` in their
    system prompt; every agent gets the briefing-aware rule line (briefing_mode) so arms differ only in who holds it.
    The briefing never enters steps, so render_prefix/spans (the oracle's view) do not contain it."""
    agents = list(prefix_agents or [])
    assert len(agents) == start_agent - 1
    holders = set(holders or ()); briefing_mode = briefing is not None
    t0 = time.time(); final = None
    for i in range(start_agent, N + 1):
        a = run_agent(i, N, K, task["question"], incoming, chat, corpus, tag,
                      briefing=(briefing if i in holders else None), briefing_mode=briefing_mode)
        agents.append(a)
        if a["final"] is not None:
            final = a["final"]; break
        incoming = a["handoff"]
    return dict(task_id=task["id"], question=task["question"], gold=task["answer"], N=N, K=K,
                briefing=briefing, holders=sorted(holders),
                start_agent=start_agent, final=final, finished_by=agents[-1]["agent"] if final is not None else None,
                agents=agents, cost=sum(a["cost"] for a in agents[start_agent - 1:]),
                tokens_in=sum(a["tokens_in"] for a in agents[start_agent - 1:]),
                tokens_out=sum(a["tokens_out"] for a in agents[start_agent - 1:]),
                seconds=round(time.time() - t0, 1))

def render_prefix(agents):
    """Full visible trace of the given agents (pass-through arm and oracle input).
    Span ids: a{i}.s{n} = tool step n of agent i (thinking + call + result); a{i}.h = handoff (thinking + message)."""
    out = []
    for a in agents:
        out.append(f"===== Agent {a['agent']} =====")
        if a["incoming"] is not None:
            out.append(f"[a{a['agent']}.in incoming message]\n{a['incoming']}\n")
        n = 0
        for s in a["steps"]:
            i = a["agent"]
            if s["kind"] == "turn" and s.get("tool_calls"):
                tc = s["tool_calls"][0]; n += 1
                if s.get("reasoning"): out.append(f"[a{i}.s{n} thinking]\n{s['reasoning']}")
                out.append(f"[a{i}.s{n} call] {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})")
                if "observation" in s: out.append(f"[a{i}.s{n} result]\n{s['observation']}")
                elif tc["name"] == "finish": out.append(f"[a{i}.s{n} finish] {tc['args'].get('answer')}")
            elif s["kind"] == "turn" and s.get("text"):
                n += 1
                if s.get("reasoning"): out.append(f"[a{i}.s{n} thinking]\n{s['reasoning']}")
                out.append(f"[a{i}.s{n} text]\n{s['text']}")
            elif s["kind"] == "handoff":
                if s.get("reasoning"): out.append(f"[a{i}.h thinking]\n{s['reasoning']}")
                out.append(f"[a{i}.h handoff message]\n{s['text']}")
            elif s["kind"] == "final":
                out.append(f"[a{i}.final]\n{s.get('text') or s.get('raw')}")
        out.append("")
    return "\n".join(out)

def spans(agents, thinking=True):
    """{span_id: text} for every citable span, same ids as render_prefix. thinking=False drops the reasoning
    (tool call + result / message text only): the source allowed for factual sentences."""
    d = {}
    for a in agents:
        i = a["agent"]; n = 0
        for s in a["steps"]:
            if s["kind"] == "turn":
                n += 1
                parts = [s.get("reasoning") or ""] if thinking else []
                if s.get("tool_calls"):
                    tc = s["tool_calls"][0]
                    parts.append(f"{tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})")
                    parts.append(s.get("observation") or "")
                else:
                    parts.append(s.get("text") or "")
                d[f"a{i}.s{n}"] = "\n".join(p for p in parts if p)
            elif s["kind"] == "handoff":
                d[f"a{i}.h"] = "\n".join(p for p in [(s.get("reasoning") or "") if thinking else "", s.get("text") or ""] if p)
    return d
