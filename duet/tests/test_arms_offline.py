"""Offline tests for the arm seam (P2) — NO LLM, NO network.

Two halves:
  1. Mechanics per arm: the store fills, renders to the right agents, tools write the
     ledger, sop normalizes, down runs its bounded challenge, board_inert stays dark.
  2. The PROMPT-DIFF AUDIT (hygiene rule 8): the same scripted relay is run under
     every arm and the full wire (every request's messages + tools) is compared to
     vanilla's. Diffs may appear ONLY at the sanctioned injection points:
       a. the layer-3 shared-state block (STORE_PREAMBLE-prefixed user message)
       b. the wrap-up request on an edge (sop/down retype it)
       c. arm-owned tool schemas (board's add/revise_belief)
       d. the payload crossing an edge (successor note layer), and arm-internal
          machinery calls (extract's observer, down's challenger)
     Anything else differing = an arm leaked outside its seam -> fail.

Run:  conda run -n autogen_gc python duet/tests/test_arms_offline.py
"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness"))

import prompts
from agent import Budget
from relay import run_relay
from arms import get_addon, normalize_sop
from store import parse_belief_lines
from _fakes import FakeClient, tool_turn, text_turn

PY = ["run_python"]
_STORE_PREFIX = prompts.STORE_PREAMBLE.split("{body}")[0].split("\n")[0]


def budget():
    return Budget(10.0, 0.36, 0.89)


# A note that satisfies every arm's parser: sop headers present, high confidence so
# down does not challenge. The SAME model behaviour is scripted for every arm, so any
# wire difference is the ARM's doing, not the script's.
NOTE = ("FINDINGS: A is established\nEVIDENCE: page X\nVERDICT: probably yes\n"
        "NEXT_STEPS: verify B\nCONFIDENCE: 0.9")


def _base_script():
    return [
        tool_turn(("run_python", {"code": "print(41+1)"})),   # shift 1 spends B=1
        text_turn(NOTE),                                      # shift 1 hand-off note
        text_turn("FINAL ANSWER: done"),                      # shift 2 early finish
    ]


def _run(arm, script):
    c = FakeClient(script)
    addon = get_addon(arm)
    addon.bind(c, "m", None)
    addon.begin_task("solve it")
    r = run_relay("solve it", PY, c, "m", addon, k=2, tool_budget=1, usd_budget=budget())
    return r, c, addon


def _wire(c):
    """Every request the fake client saw: (system_content, [user/assistant/tool
    contents...], sorted tool names)."""
    out = []
    for kw in c.calls:
        msgs = kw["messages"]
        sysc = next((m["content"] for m in msgs if m["role"] == "system"), "")
        rest = [(m["role"], m.get("content") or "") for m in msgs if m["role"] != "system"]
        tools = sorted(((t.get("function") or {}).get("name") or "") for t in kw.get("tools") or [])
        out.append((sysc, rest, tools))
    return out


# ------------------------------------------------------------------------------
# 1. per-arm mechanics
# ------------------------------------------------------------------------------
def test_sop_normalizes_payload():
    # headered note -> conformant, canonical order enforced
    text, ok = normalize_sop(NOTE)
    assert ok and text.splitlines()[0].startswith("FINDINGS:"), text
    # free-text note -> kept as FINDINGS, missing fields explicit, non-conformant
    text, ok = normalize_sop("just some prose about what I found")
    assert not ok
    assert "FINDINGS: just some prose" in text and "VERDICT: (not stated)" in text
    r, c, addon = _run("sop", _base_script())
    assert r.notes[0].startswith("FINDINGS:") and "NEXT_STEPS:" in r.notes[0]
    assert addon.stats == {"sop_payloads": 1, "sop_conformant": 1}, addon.stats
    # the wrap-up ask was the typed one
    wrap = [m for kw in c.calls for m in kw["messages"]
            if m["role"] == "user" and (m.get("content") or "").startswith(
                prompts.SOP_HANDOFF_REQUEST[:60])]
    assert wrap, "SOP wrap-up prompt never reached the wire"
    # markers pass through untouched
    assert addon.edge_payload("handoff", None, prompts.TRUNCATED_MARKER) == prompts.TRUNCATED_MARKER
    print("ok  test_sop_normalizes_payload")


def test_down_challenge_consumer_decides():
    # the consumer raises a question -> producer answers -> Q/A appended to the payload
    note = "I looked into A; here is where things stand."
    script = [
        tool_turn(("run_python", {"code": "print(1)"})),      # shift 1 spends B=1
        text_turn(note),                                      # shift 1 hand-off note
        text_turn("QUESTION: which source says A holds?"),    # consumer challenges (fresh agent)
        text_turn("The 1999 archive page, section 3."),       # producer's answer
        text_turn("FINAL ANSWER: done"),                      # shift 2 early finish
    ]
    r, c, addon = _run("down", script)
    assert addon.stats.get("down_challenges") == 1, addon.stats
    # the fired ask is logged for the trace (challenges.txt)
    arts = addon.extra_artifacts()
    assert "QUESTION: which source says A holds?" in arts.get("challenges.txt", "")
    assert "ANSWER: The 1999 archive page" in arts["challenges.txt"]
    payload = r.notes[0]
    assert "which source says A holds?" in payload and "1999 archive page" in payload
    assert payload.startswith(note[:20])                      # original note kept
    # successor saw the whole exchange
    s2 = "".join(m.get("content") or "" for m in r.shifts[1].transcript if m["role"] == "user")
    assert "1999 archive page" in s2
    # the challenge is NOT gated on any confidence number (no CONFIDENCE ask on the wire)
    assert not any("CONFIDENCE:" in (m.get("content") or "")
                   for kw in c.calls for m in kw["messages"] if m["role"] == "user")
    # consumer declines -> no challenge, payload untouched
    clear = "A is settled and verified."
    script2 = [
        tool_turn(("run_python", {"code": "print(1)"})),
        text_turn(clear),
        text_turn("QUESTION: none"),                          # consumer has nothing to ask
        text_turn("FINAL ANSWER: done"),
    ]
    r2, c2, addon2 = _run("down", script2)
    assert addon2.stats.get("down_challenges") is None and addon2.stats.get("down_edges") == 1
    assert r2.notes[0] == clear
    # the decline is counted AND logged — a quiet run stays auditable
    assert addon2.stats.get("down_declines") == 1, addon2.stats
    arts2 = addon2.extra_artifacts()
    assert "DECLINED" in arts2.get("challenges.txt", "") and "'none'" in arts2["challenges.txt"]
    print("ok  test_down_challenge_consumer_decides")


def test_board_tools_write_and_render():
    script = [
        tool_turn(("add_belief", {"object": "door", "belief": "north door is locked",
                                  "confidence": 0.9})),        # shift 1, budgeted call 1
        text_turn(NOTE),                                       # note (B=1 spent)
        text_turn("FINAL ANSWER: done"),                       # shift 2 early finish
    ]
    r, c, addon = _run("board", script)
    assert addon.stats.get("beliefs_added") == 1
    entries = addon.store_json()
    assert entries[0]["object"] == "door" and entries[0]["author"] == "shift_1"
    # the writer got a confirmation observation
    obs = [m.get("content") or "" for kw in c.calls for m in kw["messages"]
           if m.get("role") == "tool"]
    assert any("Recorded b1" in o for o in obs), obs
    # the successor saw the rendered ledger as its own delimited block
    s2 = [m.get("content") or "" for m in r.shifts[1].transcript if m["role"] == "user"]
    block = [m for m in s2 if m.startswith(_STORE_PREFIX)]
    assert block and "north door is locked" in block[0] and "[b1 · shift_1]" in block[0]
    # write-tools were offered to the agents
    assert any("add_belief" in _wire(c)[i][2] for i in range(len(c.calls)))
    print("ok  test_board_tools_write_and_render")


def test_board_revise_and_retract():
    addon = get_addon("board")
    addon.bind(None, "m", None)
    addon.inject_context("shift_1", [])
    addon.run_extra_tool("add_belief", json.dumps(
        {"object": "key", "belief": "key is in drawer 3", "confidence": 0.8}))
    addon.inject_context("shift_2", [])
    out = addon.run_extra_tool("revise_belief", json.dumps(
        {"belief_id": "b1", "belief": "key is in drawer 4", "confidence": 0.9}))
    assert "Revised" in out
    active = [e for e in addon.store_json() if e["status"] == "active"]
    assert len(active) == 1 and active[0]["belief"] == "key is in drawer 4"
    assert active[0]["author"] == "shift_2" and active[0]["revises"] == "b1"
    render = addon.render()
    assert "superseded" in render and "key is in drawer 4" in render
    out = addon.run_extra_tool("revise_belief", json.dumps(
        {"belief_id": "b2", "status": "retracted"}))
    assert "Retracted" in out and "RETRACTED" in addon.render()
    # unknown id -> helpful error, not a crash
    assert "ERROR" in addon.run_extra_tool("revise_belief", json.dumps({"belief_id": "b9"}))
    print("ok  test_board_revise_and_retract")


def test_board_inert_never_renders():
    script = [
        tool_turn(("add_belief", {"object": "door", "belief": "locked", "confidence": 0.9})),
        text_turn(NOTE),
        text_turn("FINAL ANSWER: done"),
    ]
    r, c, addon = _run("board_inert", script)
    assert addon.stats.get("beliefs_added") == 1        # the write WORKED...
    s2 = [m.get("content") or "" for m in r.shifts[1].transcript if m["role"] == "user"]
    assert not any(m.startswith(_STORE_PREFIX) for m in s2), \
        "board_inert rendered its store"                # ...but nobody ever saw it
    print("ok  test_board_inert_never_renders")


def test_extract_observer_populates_ledger():
    script = [
        tool_turn(("run_python", {"code": "print(1)"}), reasoning="I suspect A is true."),
        text_turn(NOTE),                                       # shift 1 note
        text_turn("OBSERVATION: A | A is established | 0.9\n"  # objective object -> memory
                  "BELIEF: confidence | fairly sure of the answer | 0.4"),  # subjective -> belief
        text_turn("FINAL ANSWER: done"),                       # shift 2 early finish
    ]
    r, c, addon = _run("extract", script)
    entries = addon.store_json()
    assert len(entries) == 2 and entries[0]["author"] == "shift_1"
    assert entries[0]["kind"] == "observation" and entries[1]["kind"] == "belief"
    assert addon.stats == {"observer_calls": 1, "beliefs_extracted": 2}
    # the observer call carried the OBSERVER system prompt and the producer's log,
    # including its recovered <think> trace
    ob = [kw for kw in c.calls
          if any(prompts.OBSERVER_SYS[:40] in (m.get("content") or "")
                 for m in kw["messages"] if m["role"] == "system")]
    assert len(ob) == 1
    log = "".join(m.get("content") or "" for m in ob[0]["messages"] if m["role"] == "user")
    assert "I suspect A is true." in log, "recovered reasoning missing from observer input"
    # the successor saw the extracted ledger, objective object surfaced as observed memory
    s2 = [m.get("content") or "" for m in r.shifts[1].transcript if m["role"] == "user"]
    block = [m for m in s2 if m.startswith(_STORE_PREFIX)]
    assert block and "fairly sure of the answer" in block[0]
    assert "observed — A:" in block[0], block[0]
    # note payload itself untouched (extract manipulates the store, not the edge)
    assert r.notes == [NOTE]
    print("ok  test_extract_observer_populates_ledger")


def test_parse_belief_lines():
    assert parse_belief_lines("BELIEF: none") == []
    got = parse_belief_lines("junk\nOBSERVATION: door | locked | 0.8\n"
                             "BELIEF: solvable | still looks doable | 0.6\n"
                             "BELIEF: odd line no pipes")
    assert got[0] == ("observation", "door", "locked", 0.8), got
    assert got[1] == ("belief", "solvable", "still looks doable", 0.6)
    assert got[2][0] == "belief" and got[2][2] == "odd line no pipes" and got[2][3] == 0.5
    print("ok  test_parse_belief_lines")


def test_full_stores_and_renders_transcripts():
    r, c, addon = _run("full", _base_script())
    assert addon.stats.get("transcripts_stored") == 1
    s2 = [m.get("content") or "" for m in r.shifts[1].transcript if m["role"] == "user"]
    block = [m for m in s2 if m.startswith(_STORE_PREFIX)]
    assert block, "full never rendered the transcript store"
    b = block[0]
    assert prompts.FULL_TRANSCRIPT_HEADER.format(agent="shift_1") in b
    assert "print(41+1)" in b and "42" in b, "tool call/observation missing from raw log"
    assert r.notes == [NOTE]                    # edge payload untouched
    print("ok  test_full_stores_and_renders_transcripts")


# ------------------------------------------------------------------------------
# 2. the prompt-diff audit (hygiene rule 8)
# ------------------------------------------------------------------------------
def _split_solver_calls(wire):
    """(solver-and-wrapup calls, arm-machinery calls) — machinery = observer/challenger
    system prompts. Solver calls are compared position-by-position against vanilla."""
    solver, machinery = [], []
    for sysc, rest, tools in wire:
        if sysc.startswith(prompts.OBSERVER_SYS[:40]) or sysc.startswith(
                prompts.CHALLENGE_ASK_SYS[:40]) or sysc.startswith(
                prompts.CHALLENGE_ASK_REPORT_SYS[:40]):
            machinery.append((sysc, rest, tools))
        else:
            solver.append((sysc, rest, tools))
    return solver, machinery


def test_prompt_diff_audit():
    """Same scripted behaviour under every arm; the wire may differ from vanilla ONLY
    at the sanctioned injection points."""
    base = _run("vanilla", _base_script())[1]
    vw = _wire(base)
    # vanilla itself: exactly the four layers, no stray blocks, no extra tools
    for sysc, rest, tools in vw:
        assert sysc == prompts.SOLVER_SYS
        assert tools in ([], ["run_python"]), tools
        assert not any(c.startswith(_STORE_PREFIX) for _r, c in rest), \
            "vanilla wire carries a shared-state block"

    arm_scripts = {
        "full": _base_script(),
        "sop": _base_script(),
        "down": [_base_script()[0], _base_script()[1],
                 text_turn("QUESTION: none"),          # consumer declines -> minimal diff
                 _base_script()[2]],
        "board": _base_script(),
        "board_inert": _base_script(),
        "extract": [_base_script()[0], _base_script()[1],
                    text_turn("BELIEF: none"),            # observer -> empty ledger
                    _base_script()[2]],
    }
    extra_tools = {"board", "board_inert"}
    retyped_wrapup = {"sop": prompts.SOP_HANDOFF_REQUEST}

    for arm, script in arm_scripts.items():
        _r, c, _a = _run(arm, script)
        solver, machinery = _split_solver_calls(_wire(c))
        assert len(solver) == len(vw), f"{arm}: solver call count changed"
        for i, ((vs, vrest, vtools), (s, rest, tools)) in enumerate(zip(vw, solver)):
            # board arms append the sanctioned write incentive to the system prompt
            # (rule-2 bend, board only); everyone else must be byte-identical to vanilla.
            if arm in ("board", "board_inert"):
                assert s == vs + prompts.BOARD_WRITE_INCENTIVE, \
                    f"{arm}: system prompt is not vanilla + the board incentive on call {i}"
            else:
                assert s == vs, f"{arm}: system prompt differs on call {i}"
            # tools may differ only by the arm's own write-tools
            extra = set(tools) - set(vtools)
            assert not extra or (arm in extra_tools and extra <= {"add_belief", "revise_belief"}), \
                f"{arm}: unsanctioned tool change on call {i}: {extra}"
            # message-by-message: every message must match vanilla, except
            #   (a) an inserted STORE_PREFIX block, (b) the retyped wrap-up ask,
            #   (c) the successor's note layer (the payload IS the arm's product)
            vi = 0
            for role, content in rest:
                if role == "user" and content.startswith(_STORE_PREFIX):
                    continue                                   # (a) sanctioned block
                assert vi < len(vrest), f"{arm}: extra unsanctioned message on call {i}"
                vrole, vcontent = vrest[vi]
                vi += 1
                assert role == vrole, f"{arm}: role mismatch on call {i}"
                if content == vcontent:
                    continue
                if arm in retyped_wrapup and vcontent == prompts.HANDOFF_REQUEST \
                        and content == retyped_wrapup[arm]:
                    continue                                   # (b) sanctioned wrap-up
                if vcontent.startswith(prompts.SUCCESSOR_PREAMBLE[:40]) \
                        and content.startswith(prompts.SUCCESSOR_PREAMBLE[:40]):
                    continue                                   # (c) payload contents
                raise AssertionError(
                    f"{arm}: UNSANCTIONED prompt diff on call {i}:\n"
                    f"  vanilla: {vcontent[:120]!r}\n  {arm}: {content[:120]!r}")
            assert vi == len(vrest), f"{arm}: dropped a vanilla message on call {i}"
        # machinery calls only for the arms that own them
        assert not machinery or arm in ("extract", "down"), \
            f"{arm}: unexpected machinery calls"
    print("ok  test_prompt_diff_audit  (6 arms diffed against vanilla, seam holds)")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nALL {len(fns)} ARM OFFLINE TESTS PASSED")
