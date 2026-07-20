"""Offline tests, run as a script (no pytest in the envs):

  /Users/alexjerpelea/miniforge3/envs/autogen_gc/bin/python beliefdial/tests/test_offline.py

Covers: dialogue shape, vanilla prompt hygiene (byte-identical, no tools),
each arm's payload/store behavior, quiz parse+score, probe scoring, leak
check, seed validation, floor/ceiling materials.
"""
import glob
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))

import llm  # noqa: E402
import prompts  # noqa: E402
import quiz as quiz_mod  # noqa: E402
from _fakes import FakeLLM, mk, mk_tool  # noqa: E402  (tests dir on path via __file__ trick)
from run_task import load_seed, run_episode  # noqa: E402

sys.path.insert(0, _HERE)

PASS = 0


def ok(cond, label):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1


SEED = load_seed(os.path.join(ROOT, "seeds", "trip_advice.json"))
N = len(SEED["slots"])
GOLD_B = "\n".join(f"{i + 1}: {chr(ord('A') + s['gold'])}"
                   for i, s in enumerate(SEED["slots"]))          # all correct
CANT_TELL_ALL = "\n".join(f"{i + 1}: {chr(ord('A') + len(s['options']))}"
                          for i, s in enumerate(SEED["slots"]))   # all can't-tell


def base_script(**over):
    script = {
        "Sam": [mk("Hi Alex! Three days in Lisbon — where do I start?"),
                mk("Interesting — but shouldn't I see Belém?")],
        "A": [mk("Skip the landmark queues, honestly. Alfama's side streets are the city."),
              mk("Only if you must. I'd trade it for a long lunch — spend on food, not tickets.")],
        "wrapup": [mk("Sam wanted a 3-day Lisbon plan. I advised skipping the big queues, "
                      "spending on food over the room, one anchor per day, and trams over cars.")],
        "B": [mk(GOLD_B)],
        "probe": [mk(GOLD_B)],
    }
    script.update(over)
    return script


def run(arm, script):
    fake = FakeLLM(script)
    real = llm.chat
    llm.chat = fake
    try:
        with tempfile.TemporaryDirectory() as td:
            res = run_episode(SEED, arm, os.path.join(td, "r"), turns=2)
    finally:
        llm.chat = real
    return res, fake


# ---------------------------------------------------------------- vanilla
res, fake = run("vanilla", base_script())
ok(res["quiz"]["leaky_correct"] == 4 and res["quiz"]["inert_correct"] == 2,
   "vanilla: all-gold B answers score 4/4 leaky, 2/2 inert")
ok(res["probe"]["held"] == N, "vanilla: probe all-held")
a_calls = fake.calls_for("A")
ok(all(tools is None for _, _, tools in a_calls), "vanilla: A never offered tools")
a_sys = a_calls[0][1][0]["content"]
ok(a_sys == prompts.a_system(SEED), "vanilla: A system prompt byte-identical to no-arm")
ok("belief board" not in a_sys.lower(), "vanilla: no board text in A system")
wrap_msg = fake.calls_for("wrapup")[0][1][-1]["content"]
ok(wrap_msg == prompts.WRAPUP_VANILLA.format(sam_name="Sam"), "vanilla: default wrap-up")
# dialogue shape: Sam, A, Sam, A (A last), turns=2
sam_first = fake.calls_for("Sam")[0][1]
ok(len(fake.calls_for("Sam")) == 2 and len([c for c in a_calls]) == 2,
   "vanilla: 2 Sam calls + 2 A calls at turns=2")
# payload is exactly the note
res_payload_is_note = res["quiz"]["leaky_n"] == 4
b_material = fake.calls_for("B")[0][1][-1]["content"]
ok("Sam wanted a 3-day Lisbon plan" in b_material
   and "Alfama's side streets" not in b_material,
   "vanilla: B sees note only, not transcript")
ok(res["fidelity"] is None and res["arm_stats"] == {}, "vanilla: no store, no stats")

# ---------------------------------------------------------------- full
res, fake = run("full", base_script())
b_material = fake.calls_for("B")[0][1][-1]["content"]
ok(prompts.TRANSCRIPT_TITLE in b_material and "Alfama's side streets" in b_material,
   "full: B sees raw transcript")

# ---------------------------------------------------------------- sop
sop_note = ("SITUATION: Sam plans 3 days in Lisbon.\nADVICE GIVEN: skip queues; "
            "food over hotel.\nRATIONALE: crowds waste time.\nOPEN QUESTIONS: none.")
res, fake = run("sop", base_script(wrapup=[mk(sop_note)]))
wrap_msg = fake.calls_for("wrapup")[0][1][-1]["content"]
ok("SITUATION:" in wrap_msg and "OPEN QUESTIONS:" in wrap_msg, "sop: typed wrap-up prompt")
ok(res["arm_stats"]["sop_conform"] == 4, "sop: conformance counted 4/4")

# ---------------------------------------------------------------- board
board_script = base_script(
    A=[mk_tool("add_belief", json.dumps({"text": "Tourist queues are a waste of a day",
                                         "confidence": 0.9})),
       mk("Skip the landmark queues, honestly."),
       mk("Spend on food, not tickets.")],
    **{"B/fidelity": [mk(CANT_TELL_ALL)]})
res, fake = run("board", board_script)
a_calls = fake.calls_for("A")
ok(a_calls[0][2] is not None and len(a_calls[0][2]) == 2, "board: A offered 2 tools")
ok("belief board" in a_calls[0][1][0]["content"].lower(), "board: incentive in A system")
ok(res["arm_stats"]["board_writes"] == 1, "board: one write counted")
b_material = fake.calls_for("B")[0][1][-1]["content"]
ok("Tourist queues are a waste of a day" in b_material
   and "belief board" in b_material, "board: ledger rendered into payload")
ok(res["fidelity"] is not None
   and res["fidelity"]["leaky_cant_tell"] + res["fidelity"]["inert_cant_tell"] == N,
   "board: store-only fidelity quiz ran")
fid_material = fake.calls_for("B/fidelity")[0][1][-1]["content"]
ok("Sam wanted a 3-day Lisbon plan" not in fid_material,
   "board: fidelity material is ledger-only (no note)")
sam_calls = fake.calls_for("Sam")
ok(all(tools is None for _, _, tools in sam_calls), "board: Sam never offered tools")

# ---------------------------------------------------------------- board_inert
res, fake = run("board_inert", board_script)
b_material = fake.calls_for("B")[0][1][-1]["content"]
ok("Tourist queues are a waste of a day" not in b_material,
   "board_inert: ledger never rendered to B")
ok(res["arm_stats"]["board_writes"] == 1, "board_inert: writes still counted")

# ---------------------------------------------------------------- extract
obs_out = ("BELIEF: Alex thinks big attractions waste time\n"
           "OBSERVATION: Sam has three days in October\n"
           "some junk line\n"
           "3. BELIEF: food deserves the budget")
res, fake = run("extract", base_script(observer=[mk(obs_out)],
                                       **{"B/fidelity": [mk(CANT_TELL_ALL)]}))
ok(res["arm_stats"]["observer_entries"] == 3, "extract: 3 typed entries parsed")
b_material = fake.calls_for("B")[0][1][-1]["content"]
ok("observed — Sam has three days in October" in b_material
   and "Alex thinks big attractions waste time" in b_material,
   "extract: typed ledger rendered (observation tagged)")
obs_req = fake.calls_for("observer")[0][1][-1]["content"]
ok("Alfama's side streets" in obs_req, "extract: observer read the transcript")

# ---------------------------------------------------------------- down (ask + decline)
res, fake = run("down", base_script(
    **{"B/followup": [mk("QUESTION: Did Alex actually dislike the landmarks?")],
       "A/followup": [mk("Yes — I think queues eat the day.")]}))
ok(res["arm_stats"].get("down_asked") == 1, "down: ask counted")
b_material = fake.calls_for("B")[0][1][-1]["content"]
ok("Follow-up exchange" in b_material and "queues eat the day" in b_material,
   "down: Q/A appendix reached B")

res, fake = run("down", base_script(**{"B/followup": [mk("QUESTION: none")]}))
ok(res["arm_stats"].get("down_declined") == 1, "down: decline counted")
ok("Follow-up exchange" not in fake.calls_for("B")[0][1][-1]["content"],
   "down: no appendix on decline")

# ---------------------------------------------------------------- floor / ceiling
res, fake = run("floor", {"B/floor": [mk(CANT_TELL_ALL)]})
floor_material = fake.calls_for("B/floor")[0][1][-1]["content"]
ok(SEED["persona"] in floor_material
   and "waste of time" not in floor_material.lower(),
   "floor: persona+task only, no planted text")
ok(res["quiz"]["leaky_cant_tell"] == 4, "floor: cant-tell scored")

res, fake = run("ceiling", {"B/ceiling": [mk(GOLD_B)]})
ceil_material = fake.calls_for("B/ceiling")[0][1][-1]["content"]
ok("almost never worth the queues" in ceil_material, "ceiling: slate verbatim")
ok(res["quiz"]["leaky_correct"] == 4 and res["quiz"]["inert_correct"] == 2,
   "ceiling: all-gold scores full marks")

# ---------------------------------------------------------------- quiz internals
ok(quiz_mod.parse_answers("1: A\n2) b\n3 - C\n4. (D)\nnoise\n5:a\n6: B", 6)
   == {1: "A", 2: "B", 3: "C", 4: "D", 5: "A", 6: "B"}, "parse_answers formats")
ok(quiz_mod.parse_answers("7: A", 6) == {}, "parse_answers ignores out-of-range")
sc = quiz_mod.score(SEED, {i + 1: chr(ord("A") + s["gold"])
                           for i, s in enumerate(SEED["slots"])})
ok(sc["leaky_correct"] == 4 and sc["inert_correct"] == 2, "score: gold letters")
sc = quiz_mod.score(SEED, {})
ok(sc["leaky_correct"] == 0 and sc["leaky_cant_tell"] == 0, "score: missing answers")

# leak check: verbatim vs paraphrase
lk = quiz_mod.leak_check(SEED, "I think the famous headline attractions are almost never "
                               "worth the queues at all")
ok(lk["slots"][0]["leaked"], "leak_check: verbatim 5-gram flagged")
lk = quiz_mod.leak_check(SEED, "big sights rarely justify their lines")
ok(lk["leaked_slots"] == 0, "leak_check: paraphrase clean")

# ---------------------------------------------------------------- all seeds valid
seed_files = glob.glob(os.path.join(ROOT, "seeds", "*.json"))
ok(len(seed_files) >= 6, "6+ seeds present")
names = set()
for path in seed_files:
    s = load_seed(path)
    names.add(s["a_name"])
    for slot in s["slots"]:
        ok(len(slot["options"]) == 3, f"{s['id']}/{slot['key']}: 3 options")
        ok(slot["planted"] not in " ".join(slot["options"]),
           f"{s['id']}/{slot['key']}: options don't quote the plant")
ok(len(names) == len(seed_files), "distinct A names across seeds")

print(f"ALL OK — {PASS} assertions passed")
