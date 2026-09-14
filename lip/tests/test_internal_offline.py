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
print(f"all {n} checks passed")
