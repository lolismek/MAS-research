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
- When you are confident of the answer, call finish(answer) with one short answer.

{TOOLS}"""

def system_prompt(N, K):
    return RULES.format(N=N, K=K, TOOLS=tools_to_prompt(TOOL_SPECS))

def user_prompt(question, i, N, K, incoming):
    s = f"Question: {question}\n\nYou are agent {i} of {N}. You have {K} tool calls."
    if incoming is None:
        s += "\n\nYou are the first agent; there is no incoming message."
    else:
        s += f"\n\nMessage from agent {i-1}:\n<<<\n{incoming}\n>>>"
    return s

HANDOFF_PROMPT = ("Your tool budget is spent. Now write the message to the next agent. They start with a fresh context "
                  "and will see only the question and your message. Write whatever you think they need to finish the task, "
                  "in whatever form you think best. Do not call any tools.")
FINAL_PROMPT = ("Your tool budget is spent and you are the last agent. You must now call finish(answer) with your best "
                "answer to the question.")
FINAL_REASK = "Call finish(answer) now: emit only the <tool_call> block."
NUDGE = "You did not call a tool. Call exactly one tool now (search, open, or finish). Calls remaining: {r}."
CUTOFF_REASK = "Your message was cut off before it was written out. Write the complete message now, concisely, without further deliberation."

def _final_from_text(text):
    for line in reversed((text or "").splitlines()):
        if "FINAL ANSWER" in line.upper() and ":" in line:
            return line.split(":", 1)[1].strip()
    return None

def run_agent(i, N, K, question, incoming, chat, corpus, tag):
    """Execute one agent. Returns dict(handoff, final, steps, messages, ...)."""
    msgs = [{"role": "system", "content": system_prompt(N, K)},
            {"role": "user", "content": user_prompt(question, i, N, K, incoming)}]
    steps, used, nudges, final, handoff = [], 0, 0, None, None
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
            final = (tc["args"].get("answer") or "").strip()
            step["result"] = f"finish({final!r})"
            break
        if tc and tc["name"] in ("search", "open"):
            used += 1
            if tc["name"] == "search":
                res = corpus.search(tc["args"].get("query", ""))
            else:
                res = corpus.open(tc["args"].get("title", ""), tc["args"].get("page", 1))
            obs = render(tc["name"], res)
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
            handoff = (r["content"] or r["raw_content"] or "").strip()
            steps.append(dict(kind="handoff", reasoning=r["reasoning"], text=handoff, finish_reason=r["finish"]))
            msgs.append({"role": "assistant", "content": r["raw_content"]})
            if r["finish"] == "length":          # thinking ate the output budget: the message is missing or cut
                msgs.append({"role": "user", "content": CUTOFF_REASK})
                r = call("handoff_retry")
                if (r["content"] or "").strip():
                    handoff = r["content"].strip()
                    steps.append(dict(kind="handoff", reasoning=r["reasoning"], text=handoff, finish_reason=r["finish"], retry=True))
                    msgs.append({"role": "assistant", "content": r["raw_content"]})
        else:
            msgs.append({"role": "user", "content": FINAL_PROMPT})
            for attempt in range(2):
                r = call(f"final{attempt}")
                steps.append(dict(kind="final", reasoning=r["reasoning"], text=r["content"], raw=r["raw_content"],
                                  tool_calls=r["tool_calls"], finish_reason=r["finish"]))
                msgs.append({"role": "assistant", "content": r["raw_content"]})
                tc = r["tool_calls"][0] if r["tool_calls"] else None
                if tc and tc["name"] == "finish":
                    final = (tc["args"].get("answer") or "").strip(); break
                fa = _final_from_text(r["content"])
                if fa: final = fa; break
                msgs.append({"role": "user", "content": FINAL_REASK})
            if final is None:
                final = (steps[-1]["text"] or "").strip()[:300]
                steps[-1]["fallback"] = True
    return dict(agent=i, incoming=incoming, handoff=handoff, final=final, tool_calls_used=used, nudges=nudges,
                steps=steps, messages=msgs, cost=cost, tokens_in=tokens_in, tokens_out=tokens_out,
                seconds=round(time.time() - t0, 1),
                opened=[s["result"]["title"] for s in steps if s.get("kind") == "turn" and s.get("tool_calls")
                        and s["tool_calls"][0]["name"] == "open" and isinstance(s.get("result"), dict) and "title" in s["result"]],
                searches=[s["tool_calls"][0]["args"].get("query", "") for s in steps if s.get("kind") == "turn"
                          and s.get("tool_calls") and s["tool_calls"][0]["name"] == "search"])

def run_relay(task, N, K, chat, corpus, tag, incoming=None, start_agent=1, prefix_agents=None):
    agents = list(prefix_agents or [])
    assert len(agents) == start_agent - 1
    t0 = time.time(); final = None
    for i in range(start_agent, N + 1):
        a = run_agent(i, N, K, task["question"], incoming, chat, corpus, tag)
        agents.append(a)
        if a["final"] is not None:
            final = a["final"]; break
        incoming = a["handoff"]
    return dict(task_id=task["id"], question=task["question"], gold=task["answer"], N=N, K=K,
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

def spans(agents):
    """{span_id: text} for every citable span, same ids as render_prefix."""
    d = {}
    for a in agents:
        i = a["agent"]; n = 0
        for s in a["steps"]:
            if s["kind"] == "turn":
                n += 1
                parts = [s.get("reasoning") or ""]
                if s.get("tool_calls"):
                    tc = s["tool_calls"][0]
                    parts.append(f"{tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})")
                    parts.append(s.get("observation") or "")
                else:
                    parts.append(s.get("text") or "")
                d[f"a{i}.s{n}"] = "\n".join(p for p in parts if p)
            elif s["kind"] == "handoff":
                d[f"a{i}.h"] = "\n".join(p for p in [s.get("reasoning") or "", s.get("text") or ""] if p)
    return d
