"""External oracle: read a failed relay trace, pick one handoff edge i-1 -> i, write a grounded addendum.

enhance(trace)   -> dict(i, why, addendum=[{text, cite, grounded, verdict}], kept_text, cost)
conditions(trace, oracle_out, rng) -> {enhanced, original, random, passthrough}: incoming message for agent i

Grounding: every addendum sentence cites a span id (a{j}.s{n} or a{j}.h) with j < i. A sentence is kept
only if (1) the cite exists and lies before agent i and (2) a separate gpt-5.4-mini call judges the sentence
fully supported by that span. The oracle never sees the gold answer.
"""
import json, os, random, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from llm import PplxResponses
from relay import render_prefix, spans

ORACLE_MODEL = "openai/gpt-5.5"
GROUND_MODEL = "openai/gpt-5.4-mini"
MAX_WORDS = 300

ORACLE_SYS = """You are analysing a failed run of a relay of LLM agents. The relay: N agents work one after another on a
single question. Each agent starts with a fresh context, sees only the question and the written message from
the previous agent, has a small budget of tool calls (search / open over an offline Wikipedia snapshot), and
then writes a message to the next agent. The relay's final answer was wrong.

Your job is NOT to solve the question. Your job is to find information that was LOST IN PROPAGATION: information
that some agent actually had in its own loop (in a tool result, a snippet, its thinking, or its draft text) but
that did not make it into the message it handed on, and that a later agent would have needed or been helped by.

Pick ONE handoff edge, from agent i-1 to agent i (2 <= i <= last agent), where adding such lost information to the
message would most plausibly have changed the outcome. Then write an addendum for that message.

Hard constraints on the addendum:
- Every sentence must state something that appears in the trace BEFORE agent i (agents 1..i-1). You may use their
  tool results, search snippets, thinking, and messages. Nothing from agent i onwards. Nothing from your own knowledge.
  Do not compute or infer the final answer yourself; do not add facts the agents never saw.
- Lost information can be: a fact seen but dropped; an alternative value or candidate that was seen and discarded;
  a doubt or uncertainty the agent had; a dead end (searches or pages that were tried and useless); a partial plan.
- Each sentence ends with a citation to the span it comes from, using the span ids in the trace: a{j}.s{n} for tool
  step n of agent j (its thinking, call and result), a{j}.h for agent j's handoff (thinking and message).
- At most """ + str(MAX_WORDS) + """ words in total. Write it as plain notes a colleague would append to the message.

Output JSON only:
{"i": <int>, "why": "<one or two sentences: what was lost and why it mattered>",
 "addendum": [{"text": "<one sentence>", "cite": "a1.s3"}, ...]}"""

GROUND_SYS = """You check whether a sentence is fully supported by a given source span from an agent's trace.
Supported means: everything the sentence claims is stated in the span (possibly in different words). A sentence
that adds facts not in the span, or that draws a conclusion the span does not state, is NOT supported.
Reply with JSON only: {"supported": true or false, "reason": "<short>"}"""

def _json(text):
    m = re.search(r"\{.*\}", text, re.S)
    try: return json.loads(m.group(0)) if m else None
    except Exception: return None

def enhance(trace, oracle=None, grounder=None, tag="oracle"):
    oracle = oracle or PplxResponses(model=ORACLE_MODEL, effort="high", max_output_tokens=6000)
    grounder = grounder or PplxResponses(model=GROUND_MODEL, effort="low", max_output_tokens=300)
    agents = trace["agents"]
    last = agents[-1]["agent"]
    prompt = (f"Question: {trace['question']}\n\nRelay: N={trace['N']} agents, K={trace['K']} tool calls each. "
              f"Agents that ran: 1..{last}. Final answer given: {trace['final']!r} (wrong).\n\n"
              f"FULL TRACE:\n{render_prefix(agents)}\n\nNow produce the JSON.")
    r = oracle.ask(prompt, system=ORACLE_SYS, tag=f"{tag}/pick")
    j = _json(r["text"]) or {}
    cost = r["cost"]
    try: i = int(j.get("i"))
    except Exception: i = None
    if i is None or i < 2 or i > last:
        return dict(i=None, why=j.get("why"), addendum=[], kept_text="", cost=cost, raw=r["text"], error="bad i")
    sp = spans(agents)
    out = []
    for item in j.get("addendum", []):
        text, cite = str(item.get("text", "")).strip(), str(item.get("cite", "")).strip()
        m = re.match(r"a(\d+)\.(s\d+|h)$", cite)
        rec = dict(text=text, cite=cite, in_prefix=bool(m) and int(m.group(1)) < i and cite in sp, supported=None, reason=None)
        if rec["in_prefix"] and text:
            g = grounder.ask(f"SOURCE SPAN ({cite}):\n<<<\n{sp[cite][:12000]}\n>>>\n\nSENTENCE:\n{text}\n\nJSON:",
                             system=GROUND_SYS, tag=f"{tag}/ground")
            gj = _json(g["text"]) or {}
            rec["supported"] = bool(gj.get("supported")); rec["reason"] = gj.get("reason"); cost += g["cost"]
        rec["kept"] = bool(rec["in_prefix"] and rec["supported"])
        out.append(rec)
    kept = [o["text"] for o in out if o["kept"]]
    words = 0; trimmed = []
    for s in kept:
        w = len(s.split())
        if words + w > MAX_WORDS: break
        trimmed.append(s); words += w
    return dict(i=i, why=j.get("why"), addendum=out, kept_text=" ".join(trimmed), n_kept=len(trimmed),
                n_total=len(out), cost=cost, raw=r["text"])

def random_spans(agents, i, n_chars, rng):
    """Length-matched addendum of random sentences drawn from the prefix (agents < i) observations/thinking."""
    pool = []
    for a in agents:
        if a["agent"] >= i: break
        for s in a["steps"]:
            for src in (s.get("observation") or "", s.get("reasoning") or ""):
                for sent in re.split(r"(?<=[.!?])\s+", src):
                    sent = sent.strip()
                    if 30 <= len(sent) <= 300 and not sent.startswith("[") and "<tool" not in sent: pool.append(sent)
    rng.shuffle(pool)
    out, n = [], 0
    for s in pool:
        if n >= n_chars: break
        out.append(s); n += len(s) + 1
    return " ".join(out)

def conditions(trace, oracle_out, seed=0):
    """Incoming messages for agent i under each condition."""
    i = oracle_out["i"]; agents = trace["agents"]
    orig = agents[i - 2]["handoff"] or ""
    add = oracle_out["kept_text"]
    rng = random.Random(seed)
    return dict(i=i, original=orig,
                enhanced=orig + "\n\nAdditional notes:\n" + add,
                random=orig + "\n\nAdditional notes:\n" + random_spans(agents, i, len(add), rng),
                passthrough=orig + "\n\nFull record of the previous agents' work:\n" + render_prefix(agents[:i - 1]))
