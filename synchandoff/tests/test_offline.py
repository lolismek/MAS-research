"""Offline unit tests — no LLM, no Docker. Run:
    python -m pytest tests/test_offline.py -q     (from synchandoff/)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handoff.arms import (events_to_messages, normalize_sop, render_events,
                          truncate_to_budget, W_HARD_CHARS, _oracle, make_board_tools)
from harness.env import parse_pytest_output, summaries_match
from harness.env import tests_pass as _tests_pass
from harness.ledger import BeliefLedger, parse_belief_lines
from harness.splice import align_agent_context, extract_function_name
from phase2_runner import extract_fm, family_of


# --- splice -------------------------------------------------------------------
CTX = """import os

def helper():
    return 1

def target(x):
    y = x + 1
    return y

def after():
    return 2
"""
STALE = """def target(x):
    return x"""


def test_splice_replaces_block():
    out = align_agent_context(STALE, CTX)
    assert "return x\n" in out
    assert "y = x + 1" not in out
    assert "def helper():" in out and "def after():" in out


def test_splice_missing_function_returns_context():
    out = align_agent_context("def nothere():\n    pass", CTX)
    assert "def target(x):" in out and "y = x + 1" in out


def test_extract_function_name():
    assert extract_function_name(STALE) == "target"
    assert extract_function_name("not python !!") is None


# --- pytest summary parsing ---------------------------------------------------
def test_parse_pytest_variants():
    s = parse_pytest_output("=== 23 passed, 2 failed in 1.2s ===")
    assert s["passed"] == 23 and s["failed"] == 2
    s = parse_pytest_output("==== 1 error in 0.5s ====")
    assert s["error"] == 1
    s = parse_pytest_output("==== 2 passed, 1 warning in 0.1s ====")
    assert s["passed"] == 2 and s["warning"] == 1
    s = parse_pytest_output("garbage with no summary")
    assert s["total"] == 0


def test_success_rules():
    gold = {"passed": 2, "failed": 0, "error": 0}
    assert _tests_pass({"passed": 2, "failed": 0, "error": 0}, gold)
    assert not _tests_pass({"passed": 1, "failed": 1, "error": 0}, gold)
    assert summaries_match({"passed": 2, "failed": 0, "error": 0}, gold)


# --- trajectory reconstruction ------------------------------------------------
EVENTS = [
    {"type": "system", "content": "sys"},
    {"type": "user", "content": "task"},
    {"type": "assistant", "content": "", "tool_calls": [
        {"name": "bash", "arguments": "{\"command\": \"ls\"}"},
        {"name": "bash", "arguments": "{\"command\": \"pwd\"}"}]},
    {"type": "tool", "name": "bash", "arguments": {"command": "ls"}, "result": "file.py"},
    # second call never executed (budget cut mid-batch)
    {"type": "assistant", "content": "done, giving up", "tool_calls": []},
]


def test_events_to_messages_roundtrip():
    msgs = events_to_messages(EVENTS)
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "tool", "tool", "assistant"]
    tool_msgs = [m for m in msgs if m["role"] == "tool"]
    assert tool_msgs[0]["content"] == "file.py"
    assert tool_msgs[1]["content"] == "[tool budget exhausted]"
    a = [m for m in msgs if m["role"] == "assistant"][0]
    assert {t["id"] for t in a["tool_calls"]} == {t["tool_call_id"] for t in tool_msgs}


def test_render_events_clips_and_orders():
    r = render_events(EVENTS)
    assert "predecessor -> bash" in r and "observation: file.py" in r
    assert "done, giving up" in r
    long_events = [{"type": "tool", "name": "bash", "arguments": {},
                    "result": "x" * 5000}] * 10
    r = render_events(long_events, total_chars=1000)
    assert len(r) < 1200 and r.startswith("[…log start elided")


# --- budget -------------------------------------------------------------------
def test_truncate_to_budget():
    assert truncate_to_budget("short") == "short"
    t = truncate_to_budget("x" * (W_HARD_CHARS + 500))
    assert len(t) <= W_HARD_CHARS + 50 and "truncated" in t


# --- sop ----------------------------------------------------------------------
def test_normalize_sop_conformant():
    text = "FINDINGS: a\nEVIDENCE: b\nVERDICT: c\nNEXT_STEPS: d"
    out, ok = normalize_sop(text)
    assert ok and out.splitlines()[0] == "FINDINGS: a"


def test_normalize_sop_freeform():
    out, ok = normalize_sop("just some prose about the bug")
    assert not ok
    assert out.startswith("FINDINGS: just some prose")
    assert "VERDICT: (not stated)" in out


# --- ledger -------------------------------------------------------------------
def test_ledger_add_revise_render():
    led = BeliefLedger()
    e1 = led.add("A", "cause", "target() is stale", 0.9)
    led.revise("A", e1["id"], belief="target() calls a removed helper", confidence=0.95)
    r = led.render()
    assert "superseded" in r and "removed helper" in r
    led2 = BeliefLedger.from_json(json.loads(json.dumps(led.to_json())))
    assert led2.render() == r


def test_parse_belief_lines():
    text = ("OBSERVATION: cause | target() is stale | 0.9\n"
            "BELIEF: solvable | probably yes | 0.7\n"
            "BELIEF: none")
    got = parse_belief_lines(text)
    assert len(got) == 2 and got[0][0] == "observation" and got[1][3] == 0.7


def test_board_tools_handler():
    led = BeliefLedger()
    specs, handler = make_board_tools(led)
    assert {s["function"]["name"] for s in specs} == {"add_belief", "revise_belief"}
    r = handler("add_belief", {"object": "cause", "belief": "stale fn", "confidence": 1})
    assert "Recorded b1" in r and len(led.entries) == 1
    r = handler("revise_belief", {"belief_id": "nope"})
    assert r.startswith("ERROR")


# --- oracle + fm extraction ---------------------------------------------------
def test_oracle_within_budget():
    inst = {"fm_type": "function", "fm_name": "target",
            "original_code": STALE, "gold_code": "def target(x):\n    return x + 1",
            "pyfile_path": "./test_repo/pkg/mod.py"}
    note = _oracle(inst)
    assert "target" in note and "pkg/mod.py" in note
    assert len(note) <= W_HARD_CHARS + 50


def test_extract_fm():
    fm = extract_fm(CTX, "target")
    assert fm.startswith("def target(x):") and "y = x + 1" in fm
    assert "def after" not in fm
    assert extract_fm(CTX, "missing") == ""


def test_family_map():
    assert family_of("board") == "board" and family_of("board_inert") == "board"
    assert family_of("vanilla") == "plain" and family_of("floor") == "plain"
