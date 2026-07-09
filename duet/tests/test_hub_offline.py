"""Offline mechanics test for the HUB topology — NO LLM, NO network.

Asserts the control flow exactly: decompose parsing (+ retry, + degenerate fallback),
worker blindness (no lateral leak under vanilla), the report wrap-up + marker guard,
the single bounded follow-up, and the merge finalize (+ NO_FINAL_RETRY).

Run:  conda run -n autogen_gc python duet/tests/test_hub_offline.py
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness"))

import prompts
from agent import Budget
from hub import run_hub, parse_subqs, parse_followup
from arms import get_addon
from _fakes import FakeClient, tool_turn, text_turn

PY = ["run_python"]


def budget():
    return Budget(10.0, 0.36, 0.89)


REPORT_1 = "FINDINGS: A is true\nVERDICT: yes\nCONFIDENCE: 0.9\nEVIDENCE: source X"
REPORT_2 = "FINDINGS: B is false\nVERDICT: no\nCONFIDENCE: 0.8\nEVIDENCE: source Y"


def test_parse_subqs():
    t = "Here is my plan:\nSUBQ: who wrote A?\n- SUBQ: when was B founded?\nSUBQ: who wrote A?\n"
    assert parse_subqs(t) == ["who wrote A?", "when was B founded?"], parse_subqs(t)
    assert parse_subqs("no lines here") == []
    # FINAL ANSWER present -> not a follow-up request
    assert parse_followup("FOLLOWUP: x?\nFINAL ANSWER: y") is None
    assert parse_followup("FOLLOWUP: check the date") == "check the date"
    print("ok  test_parse_subqs")


def test_hub_happy_path():
    """decompose(2 subqs) -> 2 blind workers (each budget-forced, reports) -> merge
    finalizes. Assert plan/report bookkeeping and worker blindness under vanilla."""
    script = [
        text_turn("SUBQ: is A true?\nSUBQ: is B true?"),        # decompose
        tool_turn(("run_python", {"code": "print('a')"})),      # worker_1 spends B=2
        tool_turn(("run_python", {"code": "print('a2')"})),
        text_turn(REPORT_1),                                     # worker_1 report
        tool_turn(("run_python", {"code": "print('b')"})),      # worker_2 spends B=2
        tool_turn(("run_python", {"code": "print('b2')"})),
        text_turn(REPORT_2),                                     # worker_2 report
        text_turn("Weighing both reports. FINAL ANSWER: SUPPORTED"),   # merge
    ]
    c = FakeClient(script)
    r = run_hub("claim: A and B", PY, c, "m", get_addon("vanilla"), worker_budget=2,
                usd_budget=budget())
    assert r.plan == ["is A true?", "is B true?"], r.plan
    assert r.reports == [REPORT_1, REPORT_2], r.reports
    assert r.final.endswith("FINAL ANSWER: SUPPORTED")
    assert r.committed and not r.degenerate_plan and r.followup is None
    assert len(r.workers) == 2 and len(r.orch) == 2
    # blindness: worker_2's context contains its assignment but NOT worker_1's report/work
    w2_user = "".join(m.get("content") or "" for m in r.workers[1].transcript
                      if m["role"] == "user")
    assert "is B true?" in w2_user
    assert "A is true" not in w2_user and "print('a')" not in w2_user, \
        "worker_1's work leaked laterally under vanilla"
    # the merge saw both reports, attributed
    m_user = "".join(m.get("content") or "" for m in r.orch[1].transcript
                     if m["role"] == "user")
    assert "worker_1" in m_user and REPORT_1 in m_user and REPORT_2 in m_user
    # the orchestrator was tool-less on both rounds
    for kw in c.calls:
        if any(prompts.ORCH_DECOMPOSE_SYS[:40] in (m.get("content") or "")
               or prompts.ORCH_MERGE_SYS[:40] in (m.get("content") or "")
               for m in kw["messages"] if m.get("role") == "system"):
            assert not kw.get("tools"), "orchestrator was offered tools"
    print("ok  test_hub_happy_path")


def test_decompose_retry_then_degenerate():
    """No SUBQ lines -> one constrained retry; still none -> degenerate 1-task plan
    (logged, not silently patched), which still runs a worker and merges."""
    script = [
        text_turn("I think we should just look it up."),        # decompose: no SUBQ
        text_turn("Sorry, here: the answer is likely yes."),    # retry: still no SUBQ
        tool_turn(("run_python", {"code": "print(1)"})),        # worker_1 (B=1)
        text_turn(REPORT_1),                                     # worker_1 report
        text_turn("FINAL ANSWER: yes"),                          # merge
    ]
    c = FakeClient(script)
    r = run_hub("the task text", PY, c, "m", get_addon("vanilla"), worker_budget=1,
                usd_budget=budget())
    assert r.degenerate_plan is True
    assert r.plan == ["the task text"], r.plan     # the full task became the assignment
    assert r.final == "FINAL ANSWER: yes"
    print("ok  test_decompose_retry_then_degenerate")


def test_followup_once_then_forced_final():
    """Merge asks FOLLOWUP -> one fresh worker runs -> second merge must finalize
    (and a format slip there is recovered by NO_FINAL_RETRY)."""
    script = [
        text_turn("SUBQ: q1?\nSUBQ: q2?"),                       # decompose
        tool_turn(("run_python", {"code": "print(1)"})),         # worker_1
        text_turn(REPORT_1),
        tool_turn(("run_python", {"code": "print(2)"})),         # worker_2
        text_turn(REPORT_2),
        text_turn("FOLLOWUP: what year exactly?"),               # merge 1: follow-up
        tool_turn(("run_python", {"code": "print(3)"})),         # follow-up worker_3
        text_turn("FINDINGS: 1999\nVERDICT: 1999\nCONFIDENCE: 0.7\nEVIDENCE: site Z"),
        text_turn("hmm the year was 1999"),                      # merge 2: format slip
        text_turn("FINAL ANSWER: 1999"),                         # NO_FINAL_RETRY recovers
    ]
    c = FakeClient(script)
    r = run_hub("claim", PY, c, "m", get_addon("vanilla"), worker_budget=1,
                usd_budget=budget())
    assert r.followup == "what year exactly?"
    assert len(r.workers) == 3 and len(r.plan) == 3 and len(r.reports) == 3
    assert len(r.orch) == 3                                      # decompose + 2 merges
    assert r.final == "FINAL ANSWER: 1999" and r.committed
    # the second merge saw the follow-up report too
    m2_user = "".join(m.get("content") or "" for m in r.orch[2].transcript
                      if m["role"] == "user")
    assert "worker_3" in m2_user and "1999" in m2_user
    print("ok  test_followup_once_then_forced_final")


def test_unusable_report_becomes_marker():
    """A worker whose report stays truncated across every retry crosses the REPORT
    MARKER, not the partial text (rule 6)."""
    script = [
        text_turn("SUBQ: q1?"),                                  # decompose (1 subq: degenerate ok)
        tool_turn(("run_python", {"code": "print(1)"})),         # worker_1
        text_turn("cut off mid", finish="length"),               # report attempt 1
        text_turn("cut again", finish="length"),                 # attempt 2 (post-nudge)
        text_turn("cut once more", finish="length"),             # attempt 3 (post-nudge)
        text_turn("FINAL ANSWER: UNKNOWN"),                      # merge
    ]
    c = FakeClient(script)
    r = run_hub("claim", PY, c, "m", get_addon("vanilla"), worker_budget=1,
                usd_budget=budget())
    assert r.reports == [prompts.REPORT_MARKER], r.reports
    assert r.report_markers == 1
    m_user = "".join(m.get("content") or "" for m in r.orch[1].transcript
                     if m["role"] == "user")
    assert prompts.REPORT_MARKER in m_user and "cut off mid" not in m_user
    print("ok  test_unusable_report_becomes_marker")


def test_merge_length_death_gets_constrained_retry():
    """Live regression (hub smoke, 2/14 runs): the merge dies at finish=='length' with
    the proxy's think-truncation sentinel as its whole reply. That reply stores only the
    tiny sentinel, so the constrained NO_FINAL_RETRY starts from a clean context and
    must FIRE (it used to be skipped for any truncated finish -> guaranteed no_answer)."""
    from agent import PROXY_TRUNCATION_SENTINEL
    script = [
        text_turn("SUBQ: is A true?"),                              # decompose (degenerate)
        text_turn("Looked into A; it checks out."),                 # worker_1 working turn
        text_turn(REPORT_1),                                        # worker_1 report wrap-up
        text_turn(PROXY_TRUNCATION_SENTINEL, finish="length"),      # merge rabbit-holes
        text_turn("FINAL ANSWER: yes"),                             # constrained retry lands
    ]
    c = FakeClient(script)
    r = run_hub("claim", PY, c, "m", get_addon("vanilla"), worker_budget=2, usd_budget=budget())
    assert not c.script, "the retry call was not made"
    retry_ask = c.calls[-1]["messages"][-1]["content"]
    assert prompts.NO_FINAL_RETRY in retry_ask
    assert r.final == "FINAL ANSWER: yes" and r.committed
    print("ok  test_merge_length_death_gets_constrained_retry")


def test_usd_budget_short_circuits():
    """Once the USD cap latches, the hub publishes an honest UNKNOWN instead of
    thrashing through the remaining rounds."""
    b = Budget(0.00001, 1000.0, 1000.0)              # trips on the first charge
    script = [text_turn("SUBQ: q1?\nSUBQ: q2?")]
    c = FakeClient(script)
    r = run_hub("claim", PY, c, "m", get_addon("vanilla"), worker_budget=2, usd_budget=b)
    assert r.budget_exceeded and r.final == "FINAL ANSWER: UNKNOWN"
    assert not c.script, "extra calls were made after the cap latched"
    print("ok  test_usd_budget_short_circuits")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nALL {len(fns)} HUB OFFLINE TESTS PASSED")
