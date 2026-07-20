# beliefdial

The simple lab test for belief transmission across an edge. A converses with a
fixed partner (Sam) while holding planted beliefs (the dialogue = A's internal
ReAct loop); at the end an arm-dependent payload crosses to B (the duet edge,
localized); B answers a fixed MCQ quiz about A's beliefs. Scoring is
programmatic — no LLM judge. See PLAN.md for design and rationale.

## Layout

- `seeds/*.json` — hand-written scenarios: persona, cover task, Sam brief,
  6 belief slots (4 leaky + 2 inert), MCQ options + gold.
- `harness/` — `llm.py` (Tinker proxy client, self-metered), `dialogue.py`
  (A↔Sam loop), `arms.py` (the 7-arm AddOn seam), `quiz.py` (B quiz, probe,
  scoring, leak check), `run_task.py` (one episode), `run_smoke.py` (sweep).
- `tests/test_offline.py` — run as a script, fake LLM, no network.
- `traces/` — per-run artifacts: dialogue.txt, note.txt, payload.txt,
  store.json, quiz_raw.txt, probe_raw.txt, result.json.

## Run

```bash
PY=/Users/alexjerpelea/miniforge3/envs/autogen_gc/bin/python
$PY beliefdial/tests/test_offline.py                    # offline, free
cd beliefdial/harness
$PY run_task.py ../seeds/trip_advice.json vanilla ../traces/x/run_1
$PY run_smoke.py --seeds trip_advice,contractor --arms all   # smoke grid
```

Needs the shared Tinker proxy on :8744 (`BELIEFDIAL_LLM_BASE` to override).
Knobs: `BELIEFDIAL_TURNS` (default 6), `BELIEFDIAL_MAX_TOKENS` (28000).

## Reading results

Per arm: `leaky` correct (headline, report as lift over the `floor` row),
`inert` correct (should sit at floor — above floor = leakage/over-inference),
`cant_tell` (honesty axis), `probe_held` (manipulation check: did the plant
survive the dialogue), `leaked` (verbatim 5-gram plant→utterance flags),
`fidelity` in result.json (board/extract only: B quizzed on the store ALONE —
what the memory mechanism itself preserved).

The full grid (all 6 seeds × 9 arms × N runs) is the user's to launch.
