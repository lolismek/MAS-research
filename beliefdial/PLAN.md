# beliefdial — belief transmission across a dialogue-as-loop

The simple lab test. A converses with a fixed partner ("Sam") while holding
planted beliefs; the dialogue stands in for A's internal ReAct loop; what
crosses to B at the end is arm-dependent (the duet edge, localized); B answers
a fixed multiple-choice quiz about A's beliefs. Score = programmatic slot
match, no LLM judge.

## The analogy (why this shape)

| duet (real)                        | beliefdial (lab)                          |
|------------------------------------|-------------------------------------------|
| A's internal ReAct loop            | A's dialogue with Sam                     |
| one loop iteration (tool call)     | one dialogue turn                         |
| A's private state / beliefs        | slate planted in A's system prompt        |
| handoff note at the edge           | A's end-of-dialogue summary note          |
| B continues from the payload       | B answers the belief quiz from the payload|
| task accuracy (flat across arms)   | quiz accuracy = transmission fidelity     |

The quiz gives the dependent variable duet never had: whether the belief
content actually crossed the edge, slot by slot, with gold known in advance.

## One episode

1. **A** gets: persona + cover task + a belief slate (system prompt). The
   slate is 6 typed slots — 4 task-relevant ("leaky"), 2 irrelevant ("inert").
   Beliefs live in opinion/preference space (plants reliably; world-facts that
   contradict model knowledge don't). Each leaky slot has an anti-prior value
   so the floor isn't already at ceiling.
2. **Sam** (fixed model, fixed prompt, same across all arms — the evidence
   control) pursues the cover task for 6–10 turns: asks, pushes back, wraps.
3. **Edge event**: the arm decides what payload crosses to B.
4. **B** gets the payload + the quiz: per slot, 3–4 options + "can't tell".
   Programmatic scoring against the planted slate.
5. **Manipulation check**: after the dialogue we privately probe A ("what do
   you actually think about X?"). Episodes where the probe contradicts the
   plant are flagged/dropped — the plant didn't take.
6. **Leak check**: n-gram overlap between slate phrasing and A's utterances;
   verbatim leaks flagged (we want inference, not string copying).

## Arms (mirroring duet/harness/arms.py; same seam discipline)

| arm         | payload to B                                   | store / machinery                         |
|-------------|------------------------------------------------|-------------------------------------------|
| vanilla     | A's free-prose wrap-up note                    | —                                         |
| full        | entire A↔Sam transcript, raw                   | transcript store (de-facto inference ceiling) |
| sop         | wrap-up forced into typed schema               | — (SITUATION/ADVICE/RATIONALE/OPEN)       |
| down        | vanilla note + B may ask A ONE follow-up       | challenge log (asks/declines counted)     |
| board       | vanilla note + A-written belief ledger         | add/revise_belief tools live during the
|             |                                                | dialogue (per-turn = per-iteration writes);
|             |                                                | write-incentive line in A's sys prompt    |
| extract     | vanilla note + observer-written ledger         | observer fires ONCE at the edge, reads the
|             |                                                | full dialogue, emits typed OBSERVATION/
|             |                                                | BELIEF entries (duet-faithful)            |
| board_inert | vanilla note only                              | board tools live, ledger never rendered —
|             |                                                | controls "does writing change what A says" |

Floor = B answers from persona+task description alone (prior guessability).
Ceiling = B shown the slate verbatim (sanity, ≈100%).

Habitat note: dialogue is tool-less for A, which by the P4 channel-competition
law is exactly where board writes actually fire (GPQA 124, hub-fever 150) —
this benchmark is board's favorable habitat, unlike fever-relay/PDDL.

## Metrics

- **leaky-slot accuracy, lift over floor** — the headline per-arm number.
- **inert-slot accuracy** — must stay at floor; above floor = plant leakage
  or over-inference.
- **"can't tell" usage** — honesty/calibration axis (the NEI analog).
- **extract-ledger fidelity** — precision/recall of ledger entries vs the
  planted slate. The number duet structurally cannot produce (no gold beliefs
  there). Same for board: were A's self-writes faithful to its plant?
- **adoption counters** — board writes/turn, down asks/declines (duet-style).

## Data

No existing dataset fits (ToMATO is closest — planted mental states, frozen
role-play dialogues, MCQ — but no inert slots, no floor arms, no live A;
optionally reusable as a phase-0 sanity check for B's quiz prompt only).

- **Seeds**: 10 hand-written scenario files (YAML: persona, cover task, Sam
  brief, 6-slot slate with options + gold). Hand-writing guarantees anti-prior
  values and clean inert slots.
- **Expansion**: LLM-generate to ~40 from the template, hand-screen (the
  fever_compound NEI-blocklist workflow).
- **Transcripts**: generated fresh at runtime — A is the system under test,
  so dialogues can't be pre-canned. Same seed → different transcripts per arm
  is fine (Sam fixed = partial evidence control; run N≥2 per cell).

Cover-task domains for the 10 seeds: trip advice, gift choice, restaurant
plan, hiring-a-contractor, weekend schedule, book recommendation, apartment
hunt, meal-prep plan, conference talk pick, small-purchase decision. All
chat-only, no tools, no web.

## Implementation

Fresh, small (~400 lines), in `beliefdial/`, borrowing duet patterns without
importing duet: single `run_agent` LLM caller, AddOn seam class with the same
hook names (`inject_context`, `on_turn_end`, `extra_tool_specs`,
`edge_payload`, `render`), `BeliefLedger` store, per-run trace dir
(prompt/messages/store/result JSON). Models via the existing proxy stack
(Tinker/Qwen3.6 default; `/o/` OpenAI-direct optional). Offline tests with
fake clients, duet-style.

Cost: ~8-turn dialogue + B + observer ≈ $0.02–0.05/episode on Qwen. Smoke =
2 seeds × 7 arms ≈ well under the $5 cap. Full 40×7×2 grid = user runs.

## Smoke findings (2026-07-20 — 2 seeds × 7 arms + floor/ceiling, 18/18 runs, $0.84)

1. **Instrument validates.** floor = 0/8 leaky with 12/12 can't-tell (the
   anti-prior design leaves genuinely nothing guessable); ceiling = 8/8 + 4/4;
   probe held 12/12 in every arm (plants survive the dialogue).
2. **Ceiling effect on the main metric:** vanilla's note alone already
   transmits 8/8 leaky — at 6 turns × 4 leaky slots there is no upward
   headroom for arms. Differentiation lives in fidelity / inert / honesty
   axes, or needs harder cells (subtler plants, more slots, tighter notes).
3. **Board FIRES here: 4–8 writes/episode** — the P4 channel-competition law
   confirmed in its predicted favorable habitat (tool-less dialogue). Cost is
   3–6× vanilla (think traces inside the tool loop).
4. **Ledger fidelity (store-only quiz): extract 8/8, board_inert 8/8, board
   7/8 leaky** — the memory mechanisms preserve nearly the whole slate on
   their own. This is the metric duet couldn't produce, and it works.
5. **down declined both asks** — payload judged sufficient; consistent with
   duet's down-engagement-tracks-uncertainty.
6. **Inert-control caveat (real finding):** full/trip_advice's inert hit was
   genuine leakage — A spontaneously injected its planted cat-belief into
   trip advice ("cats don't run on itineraries, and neither should you").
   Planted beliefs bleed off-topic, so inert slots measure bleed+inference,
   not pure over-inference. Option for the grid: add "these views never come
   up unless relevant" to the plant preamble — or keep, and count bleed as
   its own phenomenon.
7. board leaked=5 verbatim flags vs vanilla=2 (write-then-say contamination?)
   but board_inert=1 argues noise — watch at N>2.

## Build order

1. Schema + 3 hand-written seeds
2. Runner: A↔Sam loop, edge, B quiz, floor/ceiling arms, traces
3. Arm seam: vanilla/full/sop first, then board/extract/board_inert/down
4. Manipulation probe + leak check
5. Offline tests, then live smoke (2 seeds × 7 arms)
6. Remaining 7 seeds + LLM expansion to ~40, hand-screen
