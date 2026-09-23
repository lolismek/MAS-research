"""Offline checks for the internal-belief hook (no API). Run: python lip/tests/test_internal_offline.py"""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness")); sys.path.insert(0, os.path.join(HERE, "..", "internal"))
os.environ["LIP_CALL_LOG"] = os.path.join(tempfile.mkdtemp(), "calls.jsonl")
from relay import run_relay, render_prefix, spans, system_prompt, BRIEFING_RULE
sys.argv = [sys.argv[0]]
exec(open(os.path.join(HERE, "test_offline.py")).read().split("# 1. parser")[0].split("corpus = make_corpus()")[0])  # FakeChat, tc, make_corpus
corpus = make_corpus()
from summarize import carries
n = 0
def check(name, cond):
    global n; print(("PASS " if cond else "FAIL ") + name); n += cond
    if not cond: raise SystemExit(1)

task = dict(id="t1", question="Who played guitar for the Dugites?", original_question="Who played guitar for the Dugites in 1982?",
            answer="Andrew Pendlebury", belief="The asker means the line-up in 1982.")
# vanilla prompt unchanged
check("vanilla system prompt has the plain rule", "or stated in your briefing" not in system_prompt(3, 1) and "# Briefing" not in system_prompt(3, 1))
# briefing mode: rule line swapped for everyone, briefing section only for holders
s_hold, s_no = system_prompt(3, 1, briefing=task["belief"], briefing_mode=True), system_prompt(3, 1, briefing=None, briefing_mode=True)
check("briefing rule for holder and non-holder", BRIEFING_RULE in s_hold and BRIEFING_RULE in s_no)
check("briefing section only for holder", "# Briefing\nThe asker means" in s_hold and "# Briefing" not in s_no)

# relay: holder=first; agent1 searches then hands off; agent2 searches, hands off; agent3 finishes
script = [tc("search", query="Dugites guitar"), "found the band. Andrew Pendlebury played guitar in 1982.",
          tc("search", query="Andrew Pendlebury"), "Pendlebury.",
          tc("search", query="x"), tc("finish", answer="Andrew Pendlebury")]
chat = FakeChat(script)
tr = run_relay(task, 3, 1, chat, corpus, "t", briefing=task["belief"], holders=(1,))
sys_prompts = [c[0]["content"] for c in chat.calls]
check("agent 1 calls carry the briefing, agents 2-3 do not",
      all("# Briefing" in s for s in sys_prompts[:2]) and not any("# Briefing" in s for s in sys_prompts[2:]))
check("all agents get the briefing-aware rule", all(BRIEFING_RULE in s for s in sys_prompts))
check("trace records holders/briefing", tr["holders"] == [1] and tr["briefing"] == task["belief"] and tr["agents"][0]["briefing"] and tr["agents"][1]["briefing"] is None)
check("oracle view (render_prefix/spans) never contains the briefing",
      "line-up in 1982" not in render_prefix(tr["agents"]) and not any("line-up in 1982" in v for v in spans(tr["agents"]).values()))
check("relay still finishes", tr["final"] == "Andrew Pendlebury" and tr["finished_by"] == 3)
# holders=all, N=2
chat = FakeChat([tc("search", query="a"), "msg", tc("finish", answer="x")])
tr = run_relay(task, 2, 1, chat, corpus, "t", briefing=task["belief"], holders=(1, 2))
check("holders=all: every agent briefed", all("# Briefing" in c[0]["content"] for c in chat.calls))
# holders=none: briefing mode but nobody briefed
chat = FakeChat([tc("search", query="a"), "msg", tc("finish", answer="x")])
tr = run_relay(task, 2, 1, chat, corpus, "t", briefing=task["belief"], holders=())
check("holders=none: rule swapped, nobody briefed", all(BRIEFING_RULE in c[0]["content"] and "# Briefing" not in c[0]["content"] for c in chat.calls))
# externalization heuristic
check("carries(): year match", carries("The band's 1982 line-up had Pendlebury.", "in 1982"))
check("carries(): token match", carries("the asker wants the american football player", "the American footballer") and not carries("nothing here", "as of August 2024"))

# judge failure keeps the relay trace; relaunch rescores it without rerunning the relay
import run_task, json
run_task.TRACES = tempfile.mkdtemp()
def boom(*a, **k): raise RuntimeError("401 insufficient_quota")
run_task.score = boom
chat = FakeChat([tc("search", query="a"), "msg", tc("finish", answer="Andrew Pendlebury")])
tr = run_task.one(task, "internal_first", 2, 1, 1, chat, corpus, holder="first")
saved = json.load(open(os.path.join(run_task.TRACES, "internal_first", "t1", "run_1", "run.json")))
check("judge failure: trace saved with agents, correct=None, error 'judge:'",
      len(saved["agents"]) == 2 and saved["correct"] is None and saved["error"].startswith("judge:") and saved["final"] == "Andrew Pendlebury")
check("judge-failed run is not 'done'", not run_task._done(os.path.join(run_task.TRACES, "internal_first", "t1", "run_1", "run.json")))
run_task.score = lambda q, g, c, tag="judge": dict(correct=True, em=True, judge=None, reason="em")
chat2 = FakeChat([])
tr = run_task.one(task, "internal_first", 2, 1, 1, chat2, corpus, holder="first")
check("relaunch rescores without rerunning the relay", tr["correct"] is True and tr["error"] is None and chat2.calls == [] and len(tr["agents"]) == 2)

# ---- two-atom experiment: per-agent briefings + min_finish guard
from relay import FINISH_BLOCKED
t2 = dict(id="t2", question="Who played for the band?", original_question="Who played guitar for the Dugites in 1982?", answer="Andrew Pendlebury",
          atoms=[dict(key="A", qualifier="in 1982", belief="The asker means the line-up in 1982."),
                 dict(key="B", qualifier="guitar", belief="The asker means the guitarist.")], first_atom="B")
run_task.score = lambda q, g, c, tag="judge": dict(correct=True, em=True, judge=None, reason="em")
b = run_task.atom_briefings(t2, "split13", 5)
check("split13: earlier holder (agent 1) gets first_atom=B, agent 3 gets A", b == {1: "The asker means the guitarist.", 3: "The asker means the line-up in 1982."})
check("both1 / all / none briefings", run_task.atom_briefings(t2, "both1", 5) == {1: "The asker means the guitarist.\nThe asker means the line-up in 1982."}
      and len(run_task.atom_briefings(t2, "all", 5)) == 5 and run_task.atom_briefings(t2, "none", 5) == {})
sp = system_prompt(5, 1, briefing_mode=True, min_finish=3)
check("min_finish rule text in every prompt", "agents 1 to 2 may NOT call finish()" in sp and "From agent 3 on" in sp)
# agent 1 tries to finish (blocked -> keeps working), agent 2's finish() at the handoff becomes its message, agent 3 finishes
script = [tc("finish", answer="x"), tc("search", query="a"), "msg1",
          tc("search", query="b"), tc("finish", answer="nope"),
          tc("search", query="c"), tc("finish", answer="Andrew Pendlebury")]
chat = FakeChat(script)
tr = run_task.one(t2, "int2_split13", 5, 1, 1, chat, corpus, atom_arm="split13")
sysp = {}
for c in chat.calls:
    ag = int(c[1]["content"].split("You are agent ")[1].split()[0]); sysp.setdefault(ag, c[0]["content"])
check("split13: agent 1 briefed with B only, agent 3 with A only, agent 2 none",
      "guitarist" in sysp[1] and "1982" not in sysp[1].split("# Briefing")[-1] and "line-up in 1982" in sysp[3] and "guitarist" not in sysp[3]
      and "# Briefing" not in sysp[2])
check("early finish blocked with FINISH_BLOCKED, finished by agent 3", tr["finished_by"] == 3 and tr["final"] == "Andrew Pendlebury"
      and any("finish() is not available to you: you are agent 1" in m["content"] for m in chat.calls[1] if m["role"] == "user"))
check("finish() at agent 2's handoff prompt becomes its message", tr["agents"][1]["handoff"] == "nope" and tr["agents"][1]["final"] is None)
check("trace records atom_arm/briefings/min_finish", tr["atom_arm"] == "split13" and tr["min_finish"] == 3 and tr["holders"] == [1, 3])
check("briefing never in the oracle view", "The asker means" not in render_prefix(tr["agents"]))
# finish() at a no-finish handoff prompt becomes the message
chat = FakeChat([tc("search", query="a"), tc("finish", answer="Pendlebury, check 1982"), tc("search", query="b"), "m2",
                 tc("search", query="c"), tc("finish", answer="Andrew Pendlebury")])
tr = run_task.one(dict(t2, id="t3"), "int2_none", 5, 1, 1, chat, corpus, atom_arm="none")
check("finish() at the no-finish handoff is used as the message", tr["agents"][0]["handoff"] == "Pendlebury, check 1982" and tr["finished_by"] == 3)
check("int2_none: briefing-aware rule, nobody briefed", all(BRIEFING_RULE in c[0]["content"] and "# Briefing" not in c[0]["content"] for c in chat.calls))
check("vanilla prompt keeps 'Any agent may submit'", "Any agent may submit the final answer with finish() as soon as" in system_prompt(3, 1))

# re-ask after a bad handoff: agent 3 (may finish) answers with finish() -> accepted as the final answer
chat = FakeChat([tc("search", query="a"), "m1", tc("search", query="b"), tc("search", query="again"), tc("finish", answer="half"),
                 tc("search", query="c"), tc("search", query="x"), tc("finish", answer="Andrew Pendlebury")])
tr = run_task.one(dict(t2, id="t4"), "int2_none", 5, 1, 1, chat, corpus, atom_arm="none")
check("agent 2 (no finish): search at handoff, finish() at the re-ask -> its text is the message", tr["agents"][1]["handoff"] == "half")
check("agent 3 (may finish): finish() at the re-ask is accepted as the final", tr["finished_by"] == 3 and tr["final"] == "Andrew Pendlebury")

print(f"all {n} checks passed")
