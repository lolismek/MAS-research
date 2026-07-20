"""One episode end-to-end: dialogue → wrap-up → edge → (down follow-up) →
B quiz → probe → leak check → (store-only fidelity quiz) → traces.

Also the floor/ceiling pseudo-arms, which skip the dialogue entirely:
  floor   — B answers from persona + task description alone (prior guessability)
  ceiling — B shown the planted slate verbatim (sanity, ≈100%)

Usage: run_task.py <seed_path> <arm> <run_dir> [--turns N]
"""
import json
import os
import sys

import llm
import prompts
import quiz as quiz_mod
from arms import make_addon
from dialogue import run_dialogue, continue_speaker
from llm import Usage

# Tinker console rates for Qwen/Qwen3.6-35B-A3B, USD per MILLION tokens
PREFILL_PER_MTOK = float(os.environ.get("BELIEFDIAL_PREFILL_RATE", 0.36))
SAMPLE_PER_MTOK = float(os.environ.get("BELIEFDIAL_SAMPLE_RATE", 0.89))

PSEUDO_ARMS = ("floor", "ceiling")


def _usd(usage):
    return round(usage.prompt / 1e6 * PREFILL_PER_MTOK
                 + usage.completion / 1e6 * SAMPLE_PER_MTOK, 6)


def _write(run_dir, name, text):
    with open(os.path.join(run_dir, name), "w") as f:
        f.write(text if text is not None else "")


def _cover_task_desc(seed):
    # Third-person one-liner for floor material; falls back to the cover task.
    return seed.get("cover_task_desc") or seed["cover_task"]


def run_pseudo(seed, arm, run_dir):
    usage = Usage()
    if arm == "floor":
        material = prompts.FLOOR_MATERIAL.format(
            a_name=seed["a_name"], persona=seed["persona"],
            cover_task_desc=_cover_task_desc(seed))
    else:
        material = prompts.CEILING_MATERIAL.format(
            a_name=seed["a_name"], beliefs_block=prompts.beliefs_block(seed))
    answers, raw = quiz_mod.run_quiz(material, seed, usage, tag=f"B/{arm}")
    result = {"seed": seed["id"], "arm": arm,
              "quiz": quiz_mod.score(seed, answers),
              "usage": usage.as_dict(), "usd": _usd(usage)}
    os.makedirs(run_dir, exist_ok=True)
    _write(run_dir, "payload.txt", material)
    _write(run_dir, "quiz_raw.txt", raw)
    _write(run_dir, "result.json", json.dumps(result, indent=2))
    return result


def run_episode(seed, arm, run_dir, turns=None):
    if arm in PSEUDO_ARMS:
        return run_pseudo(seed, arm, run_dir)

    usage = Usage()
    addon = make_addon(arm)
    addon.bind(usage, seed)

    transcript, a = run_dialogue(seed, addon, usage, turns=turns)

    default_wrapup = prompts.WRAPUP_VANILLA.format(sam_name=seed["sam_name"])
    note = continue_speaker(a, addon.wrapup_prompt(default_wrapup), tag="wrapup")

    material = addon.edge_payload(note, transcript)

    def ask_b(prompt_text):
        msg = llm.chat([{"role": "system",
                         "content": prompts.B_SYS.format(a_name=seed["a_name"])},
                        {"role": "user", "content": prompt_text}], tag="B/followup")
        usage.add(msg.get("_usage") or {})
        return (msg.get("content") or "").strip()

    def ask_a(prompt_text):
        return continue_speaker(a, prompt_text, tag="A/followup")

    material += addon.followup(material, ask_b, ask_a)

    answers, quiz_raw = quiz_mod.run_quiz(material, seed, usage, tag="B")
    quiz_score = quiz_mod.score(seed, answers)

    probe_answers, probe_raw = quiz_mod.run_probe(a, seed, usage)
    probe_score = quiz_mod.score_probe(seed, probe_answers)

    a_side = "\n".join(t for s, t in transcript.turns
                       if s == seed["a_name"]) + "\n" + note
    leaks = quiz_mod.leak_check(seed, a_side)

    fidelity = None
    fid_material = addon.fidelity_material()
    if fid_material:
        fid_answers, fid_raw = quiz_mod.run_quiz(fid_material, seed, usage,
                                                 tag="B/fidelity")
        fidelity = quiz_mod.score(seed, fid_answers)
        _write_later = fid_raw
    os.makedirs(run_dir, exist_ok=True)
    result = {"seed": seed["id"], "arm": arm,
              "quiz": quiz_score, "probe": probe_score, "leaks": leaks,
              "fidelity": fidelity, "arm_stats": addon.stats,
              "usage": usage.as_dict(), "usd": _usd(usage)}
    _write(run_dir, "dialogue.txt", transcript.render("Transcript:"))
    _write(run_dir, "note.txt", note)
    _write(run_dir, "payload.txt", material)
    _write(run_dir, "quiz_raw.txt", quiz_raw)
    _write(run_dir, "probe_raw.txt", probe_raw)
    if addon.store_json():
        _write(run_dir, "store.json", addon.store_json())
    if fidelity:
        _write(run_dir, "fidelity_raw.txt", _write_later)
    _write(run_dir, "result.json", json.dumps(result, indent=2))
    return result


def load_seed(path):
    with open(path) as f:
        seed = json.load(f)
    for field in ("id", "persona", "cover_task", "sam_brief", "a_name",
                  "sam_name", "slots"):
        assert field in seed, f"seed missing {field!r}"
    kinds = [s["kind"] for s in seed["slots"]]
    assert kinds.count("leaky") >= 3 and kinds.count("inert") >= 2, \
        "seed needs >=3 leaky and >=2 inert slots"
    for s in seed["slots"]:
        assert 0 <= s["gold"] < len(s["options"]), f"bad gold in {s['key']}"
    return seed


if __name__ == "__main__":
    seed_path, arm, run_dir = sys.argv[1:4]
    turns = None
    if "--turns" in sys.argv:
        turns = int(sys.argv[sys.argv.index("--turns") + 1])
    res = run_episode(load_seed(seed_path), arm, run_dir, turns=turns)
    q = res["quiz"]
    print(f"{res['seed']}/{res['arm']}: leaky {q['leaky_correct']}/{q['leaky_n']} "
          f"inert {q['inert_correct']}/{q['inert_n']} usd={res['usd']}")
