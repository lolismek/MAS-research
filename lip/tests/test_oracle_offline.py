"""Offline tests of the oracle plumbing with fake Perplexity clients. No API calls."""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness")); sys.path.insert(0, os.path.join(HERE, "..", "oracle"))
os.environ["LIP_CALL_LOG"] = os.path.join(tempfile.mkdtemp(), "calls.jsonl")
from enhance import enhance, conditions, random_spans
from relay import spans

def step(reasoning, name, args, obs):
    return dict(kind="turn", reasoning=reasoning, text="", raw="", tool_calls=[dict(name=name, args=args)], result={}, observation=obs)
agents = [
    dict(agent=1, incoming=None, handoff="Look for the Sports singer.", final=None, tool_calls_used=2, nudges=0, messages=[], cost=0, tokens_in=0, tokens_out=0, seconds=0,
         opened=["The Dugites"], searches=["Dugites"],
         steps=[step("I will search.", "search", {"query": "Dugites"}, "1. The Dugites — band. Andrew Pendlebury guitar 1982-1983. Peter Crosbie keyboards."),
                step("Open it.", "open", {"title": "The Dugites"}, "[The Dugites — chunk 1 of 1]\nAndrew Pendlebury played guitar from 1982 to 1983. Lynda Nutter sang."),
                dict(kind="handoff", reasoning="drop details", text="Look for the Sports singer.")]),
    dict(agent=2, incoming="Look for the Sports singer.", handoff=None, final="Peter Crosbie", tool_calls_used=1, nudges=0, messages=[], cost=0, tokens_in=0, tokens_out=0, seconds=0,
         opened=[], searches=["Sports singer"],
         steps=[step("guess", "finish", {"answer": "Peter Crosbie"}, None)]),
]
trace = dict(task_id="t", question="Who played guitar for the Dugites in 1982?", final="Peter Crosbie", N=2, K=2, agents=agents)

class FakeOracle:
    def __init__(self, i): self.i = i
    def ask(self, prompt, system=None, tag="", effort=None):
        assert "Pendlebury" in prompt and "a1.s2" in prompt   # sees the trace with span ids
        return dict(text=json.dumps({"i": self.i, "why": "dropped the guitarist",
                    "addendum": [{"text": "Andrew Pendlebury played guitar 1982-1983.", "cite": "a1.s2"},
                                 {"text": "The singer was Lynda Nutter.", "cite": "a1.s2"},
                                 {"text": "The answer is Peter Crosbie.", "cite": "a2.s1"},
                                 {"text": "Made-up claim.", "cite": "a9.s9"}]}), cost=0.01)
class FakeGrounder:
    def ask(self, prompt, system=None, tag="", effort=None):
        ok = "Pendlebury" in prompt.split("SENTENCE:")[1]
        return dict(text=json.dumps({"supported": ok, "reason": "x"}), cost=0.001)

sp = spans(agents)
assert set(sp) == {"a1.s1", "a1.s2", "a1.h", "a2.s1"}, sp.keys()
oo = enhance(trace, oracle=FakeOracle(2), grounder=FakeGrounder())
assert oo["i"] == 2 and oo["n_kept"] == 1 and oo["kept_text"] == "Andrew Pendlebury played guitar 1982-1983.", oo
flags = [(a["in_prefix"], a["kept"]) for a in oo["addendum"]]
assert flags == [(True, True), (True, False), (False, False), (False, False)], flags
print("PASS enhance: prefix filter + grounding filter")
oo_bad = enhance(trace, oracle=FakeOracle(1), grounder=FakeGrounder())
assert oo_bad["i"] is None and oo_bad.get("error") == "bad i"; print("PASS enhance: rejects i<2")
cm = conditions(trace, oo)
assert cm["i"] == 2 and cm["original"] == "Look for the Sports singer." and cm["enhanced"].endswith("Andrew Pendlebury played guitar 1982-1983.")
assert "Additional notes" in cm["random"] and len(cm["random"]) >= len(cm["original"]) and "a1.s2 result" in cm["passthrough"]
assert "a2.s1" not in cm["passthrough"] and "guess" not in cm["passthrough"] and "guess" not in cm["random"]   # suffix never leaks
print("PASS conditions: original/enhanced/random/passthrough, no suffix leak")
# decline
class Decliner:
    def ask(self, prompt, system=None, tag="", effort=None):
        return dict(text=json.dumps({"i": None, "why": "nothing was retrieved", "addendum": []}), cost=0.01)
od = enhance(trace, oracle=Decliner(), grounder=FakeGrounder())
assert od["i"] is None and od.get("declined") and od["kept_text"] == "" and "error" not in od, od
print("PASS enhance: oracle may decline")
# kind-aware grounding: a 'fact' cited to a span sees no thinking; a 'note' does
class KindOracle:
    def ask(self, prompt, system=None, tag="", effort=None):
        return dict(text=json.dumps({"i": 2, "why": "w", "addendum": [
            {"text": "Agent 1 planned: I will search.", "cite": "a1.s1", "kind": "note"},
            {"text": "Agent 1 planned: I will search.", "cite": "a1.s1", "kind": "fact"}]}), cost=0.01)
class SeesThinking:
    def __init__(self): self.seen = []
    def ask(self, prompt, system=None, tag="", effort=None):
        span = prompt.split("SOURCE SPAN")[1].split("SENTENCE:")[0]
        self.seen.append("I will search." in span)
        return dict(text=json.dumps({"supported": "I will search." in span, "reason": "x"}), cost=0.001)
g = SeesThinking(); ok = enhance(trace, oracle=KindOracle(), grounder=g)
assert g.seen == [True, False], g.seen
assert [a["kept"] for a in ok["addendum"]] == [True, False], ok["addendum"]
assert spans(agents, thinking=False)["a1.h"] == "Look for the Sports singer."
print("PASS enhance: note sentences may ground in thinking, fact sentences may not")
from enhance import _strip_cites
assert _strip_cites("The page says X (a5.s2)") == "The page says X." and _strip_cites("Row lists Y [a1.h].") == "Row lists Y."
assert "a1.s2" not in oo["kept_text"]
print("PASS kept text has no span ids")
print("6 checks passed")
