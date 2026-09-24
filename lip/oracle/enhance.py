"""External oracle: read a failed relay trace, pick one handoff edge i-1 -> i, write a grounded addendum.

enhance(trace)   -> dict(i, why, addendum=[{text, cite, grounded, verdict}], kept_text, cost)
conditions(trace, oracle_out, rng) -> {enhanced, original, random, passthrough}: incoming message for agent i

Grounding: every addendum sentence cites a span id (a{j}.s{n} or a{j}.h) with j < i. A sentence is kept
only if (1) the cite exists and lies before agent i and (2) a separate gpt-5.4-mini call judges the sentence
fully supported by that span. The oracle never sees the gold answer.
"""
import json, os, random, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from llm import PplxResponses, TinkerChat, ContextTooLong
from relay import render_prefix, spans

# LIP_ORACLE=pplx (default; gpt-5.5 oracle + gpt-5.4-mini grounder via Perplexity, the 2026-09-14 N=8 batch) or
# tinker (Qwen3.5-397B oracle + grounder on Tinker; Perplexity out of quota 2026-09-23)
ORACLE_BACKEND = os.environ.get("LIP_ORACLE", "pplx")
ORACLE_MODEL, GROUND_MODEL = {"pplx": ("openai/gpt-5.5", "openai/gpt-5.4-mini"),
                              "tinker": ("Qwen/Qwen3.5-397B-A17B:peft:262144", "Qwen/Qwen3.5-397B-A17B")}[ORACLE_BACKEND]
# tinker: the 256K-context variant fits every relay trace untrimmed (longest ~125K tokens). Same weights at 64K cost 25%
# less, so a prompt that fits 64K goes there (ORACLE_SHORT) and only longer ones use 256K; the grounder sees one cited
# span per call, so it always runs at 64K
ORACLE_SHORT = "Qwen/Qwen3.5-397B-A17B" if ORACLE_BACKEND == "tinker" else None
ORACLE_MAX_TOKENS = 20000
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
If NOTHING useful was lost at any edge (e.g. the needed facts were never retrieved by any agent, or every fact seen
was carried forward), say so: output {"i": null, "why": "<why nothing was lost>", "addendum": []}. Do not invent.

Hard constraints on the addendum:
- Every sentence must state something that appears in the trace BEFORE agent i (agents 1..i-1). You may use their
  tool results, search snippets, thinking, and messages. Nothing from agent i onwards. Nothing from your own knowledge.
  Do not compute or infer the final answer yourself; do not add facts the agents never saw.
- Lost information can be: a fact seen but dropped; an alternative value or candidate that was seen and discarded;
  a doubt or uncertainty the agent had; a dead end (searches or pages that were tried and useless); a partial plan.
- Two kinds of sentence, and you must label each:
  "fact": a statement about the world. It must come from a TOOL RESULT (search result, snippet, opened page) or from
  a previous agent's MESSAGE. An agent's thinking is NOT a source for facts: something an agent merely believed or
  recalled from memory is not lost information, even if it is true.
  "note": a statement about the agents' process: an uncertainty they voiced, a candidate they considered and
  discarded, a search or page that was tried and useless, a plan. These may come from thinking.
- Each sentence ends with a citation to the span it comes from, using the span ids in the trace: a{j}.s{n} for tool
  step n of agent j (its thinking, call and result), a{j}.h for agent j's handoff (thinking and message).
- At most """ + str(MAX_WORDS) + """ words in total. Write it as plain notes a colleague would append to the message.

Output JSON only:
{"i": <int>, "why": "<one or two sentences: what was lost and why it mattered>",
 "addendum": [{"text": "<one sentence>", "cite": "a1.s3", "kind": "fact" | "note"}, ...]}"""

GROUND_SYS = """You check whether a sentence is fully supported by a given source span from an agent's trace.
Supported means: everything the sentence claims is stated in the span (possibly in different words). A sentence
that adds facts not in the span, or that draws a conclusion the span does not state, is NOT supported.
For a "fact" sentence the span contains only tool results and messages (no thinking); the fact must be stated there.
For a "note" sentence (uncertainty, discarded candidate, dead end, plan) the span may include the agent's thinking.
Reply with JSON only: {"supported": true or false, "reason": "<short>"}"""

class TinkerAsk:
    """PplxResponses.ask() interface over TinkerChat (reasoning stays in reasoning_content; text = the answer)."""
    def __init__(self, model, max_tokens, timeout):
        self.c = TinkerChat(model=model, max_tokens=max_tokens, timeout=timeout)
    def ask(self, prompt, system=None, tag="", effort=None):
        msgs = ([dict(role="system", content=system)] if system else []) + [dict(role="user", content=prompt)]
        r = self.c.chat(msgs, tag=tag, temperature=0 if "ground" in tag else None)
        return dict(text=r["content"], cost=r["cost"], latency=r["latency"], finish=r["finish"])

def default_clients():
    if ORACLE_BACKEND == "tinker":
        return TinkerAsk(ORACLE_MODEL, ORACLE_MAX_TOKENS, 600), TinkerAsk(GROUND_MODEL, 8000, 300)
    return (PplxResponses(model=ORACLE_MODEL, effort="high", max_output_tokens=6000),
            PplxResponses(model=GROUND_MODEL, effort="low", max_output_tokens=300))

def _json(text):
    m = re.search(r"\{.*\}", text, re.S)
    try: return json.loads(m.group(0)) if m else None
    except Exception: return None

def enhance(trace, oracle=None, grounder=None, tag="oracle"):
    if oracle is None or grounder is None:
        o, g = default_clients(); oracle = oracle or o; grounder = grounder or g
    agents = trace["agents"]
    last = agents[-1]["agent"]
    prompt = (f"Question: {trace['question']}\n\nRelay: N={trace['N']} agents, K={trace['K']} tool calls each. "
              f"Agents that ran: 1..{last}. Final answer given: {trace['final']!r} (wrong).\n\n"
              f"FULL TRACE:\n{render_prefix(agents)}\n\nNow produce the JSON.")
    oracle_model = getattr(getattr(oracle, "c", None), "model", ORACLE_MODEL)
    if ORACLE_SHORT and isinstance(oracle, TinkerAsk) and len(prompt) / 3 + ORACLE_MAX_TOKENS < 65536 - 2000:
        short = TinkerAsk(ORACLE_SHORT, ORACLE_MAX_TOKENS, 600)   # ~3 chars/token is a conservative estimate
        try: r = short.ask(prompt, system=ORACLE_SYS, tag=f"{tag}/pick"); oracle_model = ORACLE_SHORT
        except ContextTooLong: r = oracle.ask(prompt, system=ORACLE_SYS, tag=f"{tag}/pick")
    else:
        r = oracle.ask(prompt, system=ORACLE_SYS, tag=f"{tag}/pick")
    j = _json(r["text"]) or {}
    cost = r["cost"]
    try: i = int(j.get("i"))
    except Exception: i = None
    if j.get("i") is None and "why" in j:
        return dict(i=None, why=j.get("why"), addendum=[], kept_text="", n_kept=0, n_total=0, cost=cost, raw=r["text"], declined=True,
                    oracle_model=oracle_model, oracle_finish=r.get("finish"))
    if i is None or i < 2 or i > last:
        return dict(i=None, why=j.get("why"), addendum=[], kept_text="", n_kept=0, n_total=0, cost=cost, raw=r["text"], error="bad i")
    sp = spans(agents); sp_fact = spans(agents, thinking=False)
    out = []
    for item in j.get("addendum", []):
        text, cite = str(item.get("text", "")).strip(), str(item.get("cite", "")).strip()
        mc = re.match(r"\(?(a\d+\.(?:s\d+|h))\b", cite)     # Qwen oracle writes a1.s4.result / (a1.h): keep the span id
        if mc: cite = mc.group(1)
        kind = "note" if str(item.get("kind", "fact")).lower().startswith("note") else "fact"
        m = re.match(r"a(\d+)\.(s\d+|h)$", cite)
        rec = dict(text=text, cite=cite, kind=kind, in_prefix=bool(m) and int(m.group(1)) < i and cite in sp, supported=None, reason=None)
        if rec["in_prefix"] and text:
            src = (sp if kind == "note" else sp_fact).get(cite, "")
            g = grounder.ask(f"SENTENCE KIND: {kind}\nSOURCE SPAN ({cite}):\n<<<\n{src[:12000]}\n>>>\n\nSENTENCE:\n{text}\n\nJSON:",
                             system=GROUND_SYS, tag=f"{tag}/ground")
            gj = _json(g["text"]) or {}
            rec["supported"] = bool(gj.get("supported")); rec["reason"] = gj.get("reason"); cost += g["cost"]
        rec["kept"] = bool(rec["in_prefix"] and rec["supported"])
        out.append(rec)
    kept = [_strip_cites(o["text"]) for o in out if o["kept"]]
    words = 0; trimmed = []
    for s in kept:
        w = len(s.split())
        if words + w > MAX_WORDS: break
        trimmed.append(s); words += w
    return dict(i=i, why=j.get("why"), addendum=out, kept_text=" ".join(trimmed), n_kept=len(trimmed),
                n_total=len(out), cost=cost, raw=r["text"], oracle_model=oracle_model, ground_model=GROUND_MODEL,
                oracle_finish=r.get("finish"))

_CITE = re.compile(r"\s*[\(\[]?\ba\d+\.(?:s\d+|h)\b[\)\]]?")
def _strip_cites(t):
    """Remove inline span ids like (a5.s2) so the injected text reads like ordinary notes."""
    t = _CITE.sub("", t).strip()
    return t if t.endswith((".", "!", "?")) else t + "."

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
