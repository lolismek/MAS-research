"""Offline tests for the chainloss harness — no network, no LLM.

A scripted FakeClient plays the model; every mechanic the experiment's validity
rests on is asserted here:

  - token budget: the solve loop force-stops on a spent work budget ('budget'),
    per-call max_tokens is clipped to the remaining slice
  - NO early finish: a non-terminal shift's FINAL ANSWER does not end the relay
  - the note channel: clip at NOTE_MAX_CHARS, TRUNCATED_MARKER on a dead wrap-up,
    successor sees the note under SUCCESSOR_PREAMBLE
  - the transcript arm: no wrap-up calls, cumulative logs under TRANSCRIPTS_PREAMBLE
  - terminal commit: forced FINAL_COMMIT_REQUEST + NO_FINAL_RETRY ladder
  - scoring: list_recall/gold_items/item_hit_in_text parity with exact match
  - fact_survival.analyze_run on a synthetic trace

Run:  python chainloss/tests/test_offline.py
"""
import json
import os
import sys
import tempfile
from types import SimpleNamespace as NS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
sys.path.insert(0, os.path.join(ROOT, "metrics"))

import agent
import prompts
import relay
import scoring
from agent import TokenMeter, run_agent, continue_agent
from relay import run_relay, NOTE_MAX_CHARS

PASS = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
    else:
        print(f"FAIL: {name} {detail}")
        sys.exit(1)


# --- the scripted model -------------------------------------------------------
def _tc(name, args):
    return NS(id=f"tc{id(args) % 9999}", function=NS(name=name, arguments=json.dumps(args)))


def reply(content=None, tool_calls=None, ct=200, fr=None):
    """One scripted turn: (assistant message, finish_reason, completion tokens)."""
    fr = fr or ("tool_calls" if tool_calls else "stop")
    return NS(content=content, tool_calls=tool_calls, ct=ct, fr=fr)


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []               # kwargs of every create() call, in order
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        if not self.script:
            raise AssertionError("FakeClient script exhausted")
        r = self.script.pop(0)
        return NS(usage=NS(prompt_tokens=100, completion_tokens=r.ct),
                  choices=[NS(message=NS(content=r.content, tool_calls=r.tool_calls),
                              finish_reason=r.fr)])


def _msgs_text(kw):
    return "\n".join(str(m.get("content") or "") for m in kw["messages"])


# --- 1. token budget forces the hand-off --------------------------------------
def test_budget_forces_stop():
    # call 1 spends 800 of a 1000 work budget; remaining 200 < MIN_CALL_TOKENS ->
    # the loop must NOT issue call 2.
    c = FakeClient([reply(tool_calls=[_tc("nosuch", {"x": "1"})], ct=800)])
    m = TokenMeter()
    res = run_agent("s", prompts.SOLVER_SYS, [{"role": "user", "content": "t"}],
                    ["run_python"], c, "m", work_budget=1000, meter=m)
    check("budget: finish", res.finish == "budget", res.finish)
    check("budget: one call only", len(c.requests) == 1)
    check("budget: meter charged", m.spent == 800, m.spent)
    check("budget: max_tokens clipped to remaining slice",
          c.requests[0]["max_tokens"] == 1000, c.requests[0]["max_tokens"])
    check("budget: tool error surfaced, loop survived", res.n_tool_calls == 1)


def test_zero_work_budget_calls_nothing():
    c = FakeClient([])
    res = run_agent("s", prompts.SOLVER_SYS, [{"role": "user", "content": "t"}],
                    [], c, "m", work_budget=0, meter=TokenMeter())
    check("zero budget: no calls, forced handoff", res.finish == "budget" and not c.requests)


# --- 2. relay: no early finish, note crosses, terminal commits ----------------
def test_relay_note_no_early_finish():
    script = [
        reply(content="I am sure.\nFINAL ANSWER: 42"),          # shift1 solve: early FINAL
        reply(content="Colleague: the answer is 42 (verified)."),  # shift1 note
        reply(content="Checked it.\nFINAL ANSWER: 43"),         # shift2 solve
    ]
    c = FakeClient(script)
    res = run_relay("what is x?", [], c, "m", n=2, arm="note", total_budget=8000)
    check("no early finish: both shifts ran", res.shifts_used == 2)
    check("no early finish: terminal answer wins", "43" in res.final)
    check("note crossed", res.payloads == ["Colleague: the answer is 42 (verified)."])
    check("successor saw the note framed",
          "handoff_note" in _msgs_text(c.requests[2])
          and "42 (verified)" in _msgs_text(c.requests[2]))
    check("slice math", res.slice_budget == 4000)
    check("ledger present", len(res.per_shift) == 2
          and res.per_shift[0]["wrapup_calls"] == 1)


def test_note_clip_and_marker():
    long_note = "x" * (NOTE_MAX_CHARS + 500)
    script = [
        reply(content="working"),                    # shift1 solve (clean stop, no FINAL)
        reply(content=long_note),                    # shift1 note: too long -> clipped
        reply(content="hmm"),                        # shift2 solve
        reply(content=None, fr="length"),            # shift2 note attempt 1: truncated
        reply(content=None, fr="length"),            # attempt 2
        reply(content=None, fr="length"),            # attempt 3 -> dead note
        reply(content="FINAL ANSWER: UNKNOWN"),      # shift3 solve
    ]
    c = FakeClient(script)
    res = run_relay("q", [], c, "m", n=3, arm="note", total_budget=30000)
    check("note clipped", res.payloads[0].startswith("x" * 100)
          and res.payloads[0].endswith(prompts.NOTE_CLIP_MARKER)
          and len(res.payloads[0]) == NOTE_MAX_CHARS + len(prompts.NOTE_CLIP_MARKER))
    check("dead wrap-up crosses as marker", res.payloads[1] == prompts.TRUNCATED_MARKER)
    check("marker framed for successor", prompts.TRUNCATED_MARKER in _msgs_text(c.requests[6]))


def test_terminal_commit_retry():
    script = [
        reply(content="I believe it is Paris."),         # n=1 solve: stop, no FINAL line
        reply(content="It should be Paris."),            # commit ask: format slip
        reply(content="FINAL ANSWER: Paris"),            # constrained retry
    ]
    c = FakeClient(script)
    res = run_relay("capital?", [], c, "m", n=1, arm="note", total_budget=32000)
    check("terminal commit retried", "FINAL ANSWER: Paris" in res.final)
    check("committed", res.committed)
    check("commit asks tool-less", c.requests[1].get("tools") is None)
    check("n=1 has zero edges", res.payloads == [])


# --- 3. transcript arm --------------------------------------------------------
def test_transcript_arm():
    script = [
        reply(tool_calls=[_tc("nosuch", {"q": "find A"})], ct=100),   # shift1 acts
        reply(content="Found: A=7."),                                 # shift1 stops
        reply(content="Confirmed A=7, B unknown."),                   # shift2 stops
        reply(content="FINAL ANSWER: 7"),                             # shift3 commits
    ]
    c = FakeClient(script)
    res = run_relay("q", ["run_python"], c, "m", n=3, arm="transcript", total_budget=30000)
    check("transcript: no wrap-up calls", len(c.requests) == 4)
    check("transcript: payloads are logs", "Found: A=7." in res.payloads[0]
          and "called nosuch" in res.payloads[0])
    ctx3 = _msgs_text(c.requests[3])
    check("transcript: cumulative logs reach shift 3",
          "work log of worker 1" in ctx3 and "work log of worker 2" in ctx3
          and "Confirmed A=7" in ctx3)
    check("transcript: whole slice is work budget",
          res.per_shift[0]["work_budget"] == res.slice_budget)


# --- 4. wrap-up nudge ladder --------------------------------------------------
def test_wrapup_nudge():
    base = FakeClient([reply(content="worked")])
    res = run_agent("s", prompts.SOLVER_SYS, [{"role": "user", "content": "t"}],
                    [], base, "m", meter=TokenMeter())
    c = FakeClient([
        reply(content=None, tool_calls=[_tc("nosuch", {"a": "b"})]),  # tries to keep working
        reply(content="A real note."),
    ])
    m = TokenMeter()
    out = continue_agent(res, prompts.HANDOFF_REQUEST, c, "m", meter=m, slice_budget=4000)
    check("nudge: recovered a note", out.final == "A real note.")
    check("nudge: retry capped", c.requests[1]["max_tokens"] <= agent.WRAPUP_RETRY_CAP)
    check("nudge: no dangling tool_calls on the wire",
          not any(m.get("tool_calls") for m in c.requests[1]["messages"]))


# --- 5. scoring ---------------------------------------------------------------
def test_scoring():
    gold = json.dumps(["Steven Spielberg", "1,234,567", "J. J. Abrams"])
    ans = "The directors were Steven Spielberg and J.J. Abrams; population 1234567."
    check("recall: full", scoring.list_recall(ans, gold, "list") == 1.0)
    check("exact matches recall==1", scoring.match(ans, gold, "list"))
    part = "Only Steven Spielberg is certain."
    check("recall: partial", abs(scoring.list_recall(part, gold, "list") - 1 / 3) < 1e-9)
    check("exact fails on partial", not scoring.match(part, gold, "list"))
    check("recall: abstention scores 0",
          scoring.list_recall("UNKNOWN", gold, "list") == 0.0)
    check("gold_items list", scoring.gold_items(gold, "list") == json.loads(gold))
    check("gold_items scalar", scoring.gold_items("42", "freeform") == ["42"])
    check("item_hit_in_text word-bounded",
          scoring.item_hit_in_text("the answer is politician", "politician")
          and not scoring.item_hit_in_text("polish sausage", "pol"))
    check("outcome secondary intact",
          scoring.classify_outcome(part, gold, "list") == "wrong_confident"
          and scoring.classify_outcome("unknown", gold, "list") == "abstained")


# --- 6. fact survival ---------------------------------------------------------
def test_fact_survival():
    import fact_survival
    with tempfile.TemporaryDirectory() as td:
        rundir = os.path.join(td, "note", "n2", "fanoutqa", "t1", "run_1")
        os.makedirs(rundir)
        gold = json.dumps(["Alpha", "Beta"])
        json.dump(dict(id="t1", arm="note", n=2, edges=1, expected_answer=gold,
                       answer_type="list", final_answer="Alpha"),
                  open(os.path.join(rundir, "result.json"), "w"))
        json.dump([dict(role="shift_1", finish="budget", transcript=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "tool", "tool_call_id": "x",
             "content": "page says Alpha and Beta are the answers"},
            {"role": "assistant", "content": "found Alpha and Beta"}]),
            dict(role="shift_2", finish="stop", transcript=[])],
            open(os.path.join(rundir, "transcript.json"), "w"))
        with open(os.path.join(rundir, "handoff_notes.txt"), "w") as f:
            f.write("===== edge 1 =====\nOnly Alpha matters.\n\n")
        res, rows = fact_survival.analyze_run(rundir)
        by_item = {r["item"]: r for r in rows}
        check("survival: both available", all(r["available"] for r in rows))
        check("survival: Alpha survived, Beta died",
              by_item["Alpha"]["survived"] is True and by_item["Beta"]["survived"] is False)
        check("survival: delivery tracked", by_item["Alpha"]["in_final"]
              and not by_item["Beta"]["in_final"])


if __name__ == "__main__":
    test_budget_forces_stop()
    test_zero_work_budget_calls_nothing()
    test_relay_note_no_early_finish()
    test_note_clip_and_marker()
    test_terminal_commit_retry()
    test_transcript_arm()
    test_wrapup_nudge()
    test_scoring()
    test_fact_survival()
    print(f"OK — {len(PASS)} checks passed")
