"""Offline tests of the relay mechanics with a scripted fake model and a 3-page corpus. No API calls.
Run: python lip/tests/test_offline.py
"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
os.environ["LIP_CALL_LOG"] = os.path.join(tempfile.mkdtemp(), "calls.jsonl")
from llm import parse_tool_calls
from tools import Corpus, render, CHUNK_CHARS
from relay import run_relay, render_prefix, NUDGES
from judge import exact_match, normalize

def tc(name, **args):
    ps = "".join(f"<parameter={k}>{v}</parameter>" for k, v in args.items())
    return f"<tool_call>\n<function={name}>\n{ps}\n</function>\n</tool_call>"

class FakeChat:
    """Scripted responses: a list of raw contents, consumed in order. Records every messages list."""
    def __init__(self, script): self.script = list(script); self.calls = []
    def chat(self, messages, tag="", temperature=None):
        self.calls.append([dict(m) for m in messages])
        raw = self.script.pop(0) if self.script else "(script exhausted)"
        clean, calls = parse_tool_calls(raw)
        return dict(reasoning="thinking...", content=clean, raw_content=raw, tool_calls=calls, finish="stop",
                    prompt_tokens=10, completion_tokens=5, cost=0.0, latency=0.0)

def make_corpus():
    import bm25s
    root = tempfile.mkdtemp(); os.makedirs(os.path.join(root, "gold"))
    pages = [("The Dugites", "The Dugites were an Australian band. Andrew Pendlebury played guitar 1982-1983. " * 80),
             ("Andrew Pendlebury", "Andrew Pendlebury (born 1952) is an Australian guitarist. He was in The Sports."),
             ("Stephen Cummings", "Stephen Cummings (born 13 September 1954) is the lead singer of The Sports.")]
    with open(os.path.join(root, "pages.jsonl"), "w") as f:
        for k, (t, txt) in enumerate(pages):
            fn = f"gold/p{k}.json"; json.dump(dict(title=t, text=txt, kind="gold"), open(os.path.join(root, fn), "w"))
            f.write(json.dumps(dict(title=t, file=fn, kind="gold", n_chars=len(txt), head=txt[:200])) + "\n")
    idx = bm25s.BM25(); idx.index(bm25s.tokenize([(t + " ") * 3 + txt for t, txt in pages], stopwords="en", show_progress=False))
    idx.save(os.path.join(root, "index"))
    return Corpus(root)

corpus = make_corpus()
task = dict(id="t1", question="Who played guitar for the Dugites in 1982?", answer="Andrew Pendlebury")
n_pass = 0
def check(name, cond):
    global n_pass
    print(("PASS " if cond else "FAIL ") + name); n_pass += cond
    if not cond: raise SystemExit(1)

# 1. parser
_, calls = parse_tool_calls(tc("open", title="The Dugites", page=2) + " trailing")
check("parse xml tool call", calls == [dict(name="open", args=dict(title="The Dugites", page="2"))])

# 2. tools: search finds, open chunks, bad title errors
hits = corpus.search("Dugites guitar")
check("search hits gold page", hits[0]["title"] == "The Dugites" and len(hits) == 3)
o = corpus.open("the dugites", 2)
check("open chunking (page 2 of 2)", o["page"] == 2 and o["n_pages"] == 2 and len(o["text"]) > 0)
check("open bad title -> error text", "error" in corpus.open("Nonexistent"))

# 3. budget enforced, handoff crosses, finish by agent 2
K, N = 2, 3
script = [tc("search", query="Dugites guitar"), tc("open", title="The Dugites"),   # agent 1: 2 calls (budget)
          "CONTINUE",                                                                  # finish-or-continue turn declined
          "Findings: Dugites page says Andrew Pendlebury played guitar 1982-1983.",   # agent 1 handoff
          tc("finish", answer="Andrew Pendlebury")]                                  # agent 2 finishes
fc = FakeChat(script)
tr = run_relay(task, N, K, fc, corpus, "test")
check("finish by agent 2, final answer", tr["final"] == "Andrew Pendlebury" and tr["finished_by"] == 2 and len(tr["agents"]) == 2)
a1 = tr["agents"][0]
check("agent 1 used full budget and wrote handoff", a1["tool_calls_used"] == K and a1["handoff"].startswith("Findings"))
check("budget line shown to agent", "(tool calls remaining: 1)" in a1["messages"][3]["content"] and "remaining: 0" in a1["messages"][5]["content"])
check("handoff prompt asked after budget", a1["messages"][-2]["content"].startswith("Your tool budget is spent"))
a2msgs = fc.calls[4]
check("agent 2 sees only question + handoff", "Message from agent 1" in a2msgs[1]["content"] and "Findings" in a2msgs[1]["content"]
      and len(a2msgs) == 2 and "<tool_response>" not in a2msgs[1]["content"])
check("opened list recorded", a1["opened"] == ["The Dugites"] and a1["searches"] == ["Dugites guitar"])

# 4. nudge path: text-only turns get nudged, then treated as spent
script = ["I think I should search.", "Still thinking.", "Nothing.", "handoff text",   # agent 1: 3 text turns (2 nudges) -> spent
          tc("finish", answer="X")]
fc = FakeChat(script)
tr = run_relay(task, 2, 3, fc, corpus, "test")
a1 = tr["agents"][0]
check("nudged twice then handoff", a1["nudges"] == NUDGES + 1 and a1["handoff"] == "handoff text" and tr["final"] == "X")

# 5. last agent forced to finish; re-ask; text fallback
script = [tc("search", query="q"), "CONTINUE", "no tool here", "FINAL ANSWER: Pendlebury"]   # N=1,K=1: declined finish turn, one re-ask
fc = FakeChat(script)
tr = run_relay(task, 1, 1, fc, corpus, "test")
check("forced final via FINAL ANSWER line after re-ask", tr["final"] == "Pendlebury" and tr["finished_by"] == 1)
script = [tc("search", query="q"), tc("finish", answer="direct")]
tr = run_relay(task, 1, 1, FakeChat(script), corpus, "test")
check("finish on the free turn after the last tool call", tr["final"] == "direct" and tr["agents"][0]["tool_calls_used"] == 1)
script = [tc("search", query="q"), tc("finish", answer="early")]
tr = run_relay(task, 3, 1, FakeChat(script), corpus, "test")
check("agent 1 of 3 finishes on the free turn (no handoff)", tr["final"] == "early" and tr["finished_by"] == 1 and len(tr["agents"]) == 1)
script = [tc("search", query="q"), "I think it is settled.\n\nAnswer: 4"]
tr = run_relay(task, 3, 1, FakeChat(script), corpus, "test")
check("free turn: 'Answer:' line accepted as finish", tr["final"] == "4" and tr["finished_by"] == 1)
script = [tc("search", query="q"), "4", tc("finish", answer="4")]
tr = run_relay(task, 3, 1, FakeChat(script), corpus, "test")
check("free turn: bare text -> re-ask -> finish", tr["final"] == "4" and tr["finished_by"] == 1 and tr["agents"][0]["messages"][-2]["content"].startswith("Reply with exactly one of"))
script = [tc("search", query="q"), "4", "still text", "handoff after two", tc("finish", answer="Q")]
tr = run_relay(task, 2, 1, FakeChat(script), corpus, "test")
check("free turn: two non-answers -> handoff", tr["agents"][0]["handoff"] == "handoff after two" and tr["final"] == "Q")

# 6. resume from agent 2 with an injected message; prefix copied
prefix = [dict(agent=1, incoming=None, handoff="orig", final=None, tool_calls_used=2, nudges=0, steps=[], messages=[],
               cost=0, tokens_in=0, tokens_out=0, seconds=0, opened=[], searches=[])]
fc = FakeChat([tc("finish", answer="Y")])
tr = run_relay(task, 3, 2, fc, corpus, "test", incoming="orig\n\nADDENDUM: the guitarist is Andrew Pendlebury", start_agent=2, prefix_agents=prefix)
check("resume: agent 2 got injected message, prefix kept", "ADDENDUM" in fc.calls[0][1]["content"] and tr["agents"][0]["handoff"] == "orig"
      and tr["start_agent"] == 2 and tr["final"] == "Y")

# 7. render_prefix carries calls, observations, handoffs
script = [tc("search", query="Dugites guitar"), "CONTINUE", "handoff msg", tc("finish", answer="Z")]
tr = run_relay(task, 2, 1, FakeChat(script), corpus, "test")
rp = render_prefix(tr["agents"][:1])
check("render_prefix has call, result, handoff", "search({" in rp and "The Dugites" in rp and "[a1.h handoff message]\nhandoff msg" in rp)

# 7b. handoff that is a tool call or empty -> re-ask; malformed tool call parses
script = [tc("search", query="q"), "CONTINUE", tc("search", query="again"), "real handoff", tc("finish", answer="Z")]
tr = run_relay(task, 2, 1, FakeChat(script), corpus, "test")
check("tool-call handoff re-asked", tr["agents"][0]["handoff"] == "real handoff" and tr["final"] == "Z")
script = [tc("search", query="q"), "CONTINUE", "", "second try", tc("finish", answer="Z")]
tr = run_relay(task, 2, 1, FakeChat(script), corpus, "test")
check("empty handoff re-asked", tr["agents"][0]["handoff"] == "second try")
script = [tc("search", query="q"), "CONTINUE", tc("search", query="a"), tc("search", query="b"), tc("finish", answer="Z")]
fc = FakeChat(script); tr = run_relay(task, 2, 1, fc, corpus, "test")
check("tool call twice -> invalid empty handoff, next agent told", tr["agents"][0]["handoff"] == "" and tr["agents"][0]["handoff_invalid"]
      and "sent an empty message" in fc.calls[-1][1]["content"] and tr["final"] == "Z")
_, calls = parse_tool_calls("<tool_call>\n<function=search\n<parameter=query>\nx\n</parameter>\n</function>\n</tool_call>")
check("malformed <function=search (no >) still parses", calls and calls[0]["name"] == "search" and calls[0]["args"]["query"] == "x")

# 7c. finish used as a message -> re-ask; second invalid finish accepted in-loop
msg = "Agent 1 found X but not Y; requested next agent to find Z."
script = [tc("search", query="q"), tc("finish", answer=msg), tc("finish", answer="Andrew Pendlebury")]
tr = run_relay(task, 2, 3, FakeChat(script), corpus, "test")
check("message-like finish re-asked, then short finish accepted", tr["final"] == "Andrew Pendlebury" and tr["agents"][0]["steps"][1].get("invalid_finish"))
script = [tc("search", query="q"), tc("finish", answer=msg), "CONTINUE", "handoff ok", tc("finish", answer="Z")]
tr = run_relay(task, 2, 1, FakeChat(script), corpus, "test")
check("message-like finish on the free turn -> re-ask -> CONTINUE -> handoff", tr["agents"][0]["handoff"] == "handoff ok" and tr["final"] == "Z")

# 8. judge normalization
check("exact match normalizes", exact_match("The Beatles", "beatles.") and not exact_match("1990", "1991"))
print(f"\n{n_pass} checks passed")
