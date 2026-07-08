# duet/ — two asymmetry geometries × three mechanism families

A fresh, minimal MAS harness built to isolate **inter-agent misalignment** to its cause —
information asymmetry — in exactly two geometries, and to race mechanism families
(context / protocol / **shared belief state**) across them. The design rationale,
predictions, and full build order are in **[PLAN.md](PLAN.md)**; this README tracks what
is actually built and how to run it.

## Status

| Phase | What | State |
|---|---|---|
| **P0** | agent primitive + **RELAY** topology + `vanilla` arm + calibration | ✅ done |
| **P1** | **HUB** topology + FEVER-compound filter + FanOutQA loader | ✅ done (smoke: real 2-subq plans, conformant reports, correct merges on feverc + fanout) |
| **P2** | `store.py` + the 6 real arms + prompt-diff audit | ✅ done (audit green; board/extract/down smoke-validated live) |
| **P3** | metrics + process judges + challenge suite | ✅ machinery built; judges NOT yet validated on a hand-labeled slice; probes = starter set (12T+8S of ~40) |
| P4 | full grid (handed to user to run) | ⬜ |
| **P5** | **DIALOGUE** topology + gradient cell | ✅ built, offline-tested; runs after the core grid |

## The agent primitive (`harness/agent.py`)

`run_agent(...)` is the ONLY place an LLM is called: one ReAct inner loop (model → tool
calls → observe → …) that stops when the model stops, spends its **tool-call budget B**,
trips the repeated-action guard, or hits a truncation/backstop. `continue_agent(...)`
appends one user message to a finished agent and does a single no-tool call — this is the
wrap-up seam (the hand-off note; the last shift's forced commit), keeping the wrap-up its
own delimited message (hygiene rule 3).

Two independent budgets: **B** (tool calls) forces the hand-off so "when to hand off" is
never a confound; **usd_budget** is a per-task USD safety cap that short-circuits a runaway
task to an honest `UNKNOWN`. Hard-won guards ported from `camel/`: truncated output never
crosses an edge (a marker does), lazy context compaction under the 64k wall, and a **28k
output cap** (Qwen3.6's think trace counts against `max_tokens`; 8k truncates hard GAIA
reasoning before the answer — measured, not assumed).

### The wrap-up spiral (and why the note-yield metric exists)

Asked to *reflect* ("summarize what you established") over its raw tool dumps, Qwen3.6
re-analyzes all of them and spirals past the token cap inside `<think>` — the proxy then
returns a **non-empty truncation sentinel**, not a note. Two things were wrong and are now
fixed in `continue_agent`: (1) the sentinel was mistaken for a real note (the retry only
fired on *empty* content); (2) nothing stopped the spiral. The fix: **compact the tool
dumps to stubs before every wrap-up** (the note is written from the worker's memory of what
it found — what a real hand-off is — not by re-reading every page), treat
sentinel/`length`/empty as no-output and **re-ask** (first try at full quality, retries at a
cheap cap since a re-spiral is deterministic at temp 0). This took GAIA note-yield from
~0/6 → 5/6 and every wrap-up now finishes cleanly. The residual markers are *faithful* — a
shift that truncated early established little to hand off — and are surfaced as a
first-class **`note_yield`** axis (per-run `edges`/`edge_markers`/`note_yield`, per-cell in
`agg.py`) so any arm-to-arm gap in transfer robustness is measured, never a hidden confound.

## Topology 1 — RELAY (`harness/relay.py`)

K=3 identical shifts work one task in sequence; each is a fresh context with budget B; at
budget exhaustion a shift is asked (with its working memory intact) for a free-text
hand-off note, and the next shift starts from `[task, that note]` — **never** the
predecessor's transcript. That destroyed-context edge is the **temporal asymmetry**. The
PDDL world persists across shifts (the note carries beliefs about world state). Full
mechanics: PLAN "Topology 1".

## Topology 2 — HUB (`harness/hub.py`)

A tool-less orchestrator decomposes the task into 2–4 `SUBQ:` sub-questions; workers
investigate them BLIND to each other (fresh contexts, full task visible, sequential =
informationally parallel); each ends with a structured report (FINDINGS/VERDICT/
CONFIDENCE/EVIDENCE — the same wrap-up seam as the relay note); the orchestrator
merges, may issue at most ONE `FOLLOWUP:` worker, then must commit. Degenerate (<2
subq) plans run but are logged (`degenerate_plan`). Full mechanics: PLAN "Topology 2".

## Topology 3 — DIALOGUE (`harness/dialogue.py`)

Two identical PERSISTENT peers alternate turns (per-turn tool budget); only messages
cross, tool trails stay private, nobody's context is destroyed — the least-asymmetric
mixture case. A message with `FINAL ANSWER:` is a proposal; the peer ratifies
(`DECISION: agree` → done) or contests (once per run); hard cap T turns, then the
current agent must commit or abstain. Runs after the core grid (P5 cell).

## The arm seam (`harness/arms.py` + `harness/store.py`)

An arm is a policy over two decisions: what crosses an edge, and what is written to /
rendered from one shared store. All 7 arms are in:

| arm | edge payload | store |
|---|---|---|
| `vanilla` | natural artifact | — |
| `full` | natural artifact | producers' raw transcripts, rendered to every later agent |
| `sop` | typed FINDINGS/EVIDENCE/VERDICT/NEXT_STEPS (normalized on crossing) | — |
| `down` | + CONFIDENCE line; if < θ (0.6), ONE bounded Q/A challenge appended | — |
| `board` | natural artifact | belief ledger via in-loop `add_belief`/`revise_belief` tools |
| `extract` | natural artifact | same ledger, written by an observer call per edge (reads recovered `<think>`) |
| `board_inert` | natural artifact | write-tools live, store never rendered (confound control) |

Arms may only touch 4 sanctioned points (shared-state block, wrap-up ask, own tool
schemas, edge payload) — enforced by the **prompt-diff audit**
(`tests/test_arms_offline.py::test_prompt_diff_audit`), which runs the same scripted
relay under every arm and fails on any unsanctioned wire difference vs `vanilla`.
Arm-adoption counters (`beliefs_added`, `down_challenges`, `sop_conformant`, …) land in
each run's `result.json` (`arm_stats`) and aggregate in `agg.py`.

## Layout

```
harness/
  prompts.py    # ALL literal prompt strings (hygiene rule 7)
  agent.py      # run_agent + continue_agent — the only LLM callers (resume= for dialogue)
  tools.py      # web_search, fetch_url, run_python, read_file (+ PDDL env schemas)  [ported]
  pddl_env.py   # interactive pddlgym world (per-task, stateful)                     [ported]
  scoring.py    # LaTeX-aware + negation-safe FEVER + PDDL + FanOutQA-list scorers   [ported]
  relay.py      # the shift loop: K × budget B, forced hand-off (+ challenge initial_note)
  hub.py        # decompose → blind workers → merge (+1 follow-up)
  dialogue.py   # two persistent peers, ratify-or-contest, cap T
  store.py      # BeliefLedger + TranscriptStore + renders (rule-4 contract)
  arms.py       # the 7 policies on the AddOn seam
  run_task.py   # cell runner: (bench × topology × arm) → traces/…/run_N/
  agg.py        # scoreboard: outcomes, honesty, note-yield, plan quality, arm stats
metrics/
  judge.py      # process judges: information-survival (relay), contradiction-at-merge (hub)
challenge/
  build_temporal.py  temporal.jsonl   # planted-note probes (12; relay)
  spatial.jsonl                       # ambiguous-entity probes (8; hub)
  analyze.py                          # inheritance-rate scoreboard
tasks/
  smoke_relay.jsonl   # 3 GAIA + 2 PDDL P0 smoke slice
  smoke_hub.jsonl     # 5 FEVER-compound + 3 FanOutQA P1 smoke slice
tests/
  test_relay_offline.py  test_hub_offline.py  test_dialogue_offline.py
  test_arms_offline.py   # per-arm mechanics + the prompt-diff audit
  _fakes.py              # shared scripted fake client — NO LLM / NO network
```

Benchmarks (repo-level): `benchmarks/fever_compound/` (compound-claim filter over
FEVER; the relay↔hub bridge; open-book) and `benchmarks/fanoutqa/` (FanOutQA dev,
width 3–6; hub-native primary) — each has a `prep.py`.

## Run

The harness needs the shared Tinker proxy running (`PROXY_URL`, default
`http://127.0.0.1:8744/v1`). Web benchmarks (GAIA/FEVER/FanOutQA) run under **`autogen_gc`**;
PDDL needs **`camel_pddl`** (has `pddlgym`).

```
# offline mechanics tests (no spend)
conda run -n autogen_gc python duet/tests/test_relay_offline.py
conda run -n autogen_gc python duet/tests/test_hub_offline.py
conda run -n autogen_gc python duet/tests/test_dialogue_offline.py
conda run -n autogen_gc python duet/tests/test_arms_offline.py

# relay vanilla smoke
conda run -n autogen_gc python duet/harness/run_task.py --tasks smoke_relay.jsonl gaia_50f58759
conda run -n camel_pddl  python duet/harness/run_task.py --tasks smoke_relay.jsonl pddl_001

# hub vanilla smoke / an arm on the relay
conda run -n autogen_gc python duet/harness/run_task.py --topology hub --tasks smoke_hub.jsonl --all
conda run -n autogen_gc python duet/harness/run_task.py --tasks smoke_relay.jsonl gaia_50f58759 --arm board

# challenge probes (temporal = relay with a planted note; spatial = hub)
conda run -n autogen_gc python duet/harness/run_task.py --tasks duet/challenge/temporal.jsonl --all
conda run -n autogen_gc python duet/harness/run_task.py --topology hub --tasks duet/challenge/spatial.jsonl --all
python duet/challenge/analyze.py

# scoreboard + calibration; process judges (validate on a hand-labeled slice first!)
conda run -n autogen_gc python duet/harness/agg.py
conda run -n autogen_gc python duet/metrics/judge.py --sample 5
```

Knobs: `--topology relay|hub|dialogue` · `--arm <7 arms>` · `--k` (relay shifts /
dialogue turn cap) · `--budget` (tool calls per shift / worker / turn; defaults 8/8/4).

## P1/P2/P5 smoke results (one-task-per-cell, ~$0.06 total)

- **hub · vanilla · feverc_000**: real 2-subq decomposition, both blind workers returned
  conformant FINDINGS/VERDICT/CONFIDENCE/EVIDENCE reports, merge correct (SUPPORTS).
- **hub · vanilla · fanout_004**: correct aggregated list answer; note the orchestrator
  compressed the 5-branch fan-out into 2 sub-questions using parametric knowledge (it
  named the justices in SUBQ 2) — plan-quality is logged (`n_subqs`), watch it per-cell.
- **relay · board · pddl_001**: correct, but ledger EMPTY — zero `add_belief` calls on an
  easy 2-shift task. The camel low-write-adoption caveat carries over; adoption is
  measured (`arm_stats.beliefs_added`), expect it to bind mostly on long/hard tasks.
- **relay · extract · pddl_005**: correct; observer extracted 5 faithful beliefs
  (goal / state / strategy / next action / capabilities) and the successor saw the
  rendered block — the no-cooperation acquisition path works end-to-end.
- **relay · down · feverc_008**: early single-shift finish → no edge, challenge never
  fired (valid mechanic; exercised offline). ALSO surfaced a **benchmark caveat**: the
  claim (gold NOT ENOUGH INFO) was verifiable on today's web — FEVER NEI labels reflect
  the 2017 Wikipedia snapshot. **RESOLVED by hand-screen** (`_NEI_NOISY_IDS` in
  `benchmarks/fever_compound/prep.py`): NEI claims where every conjunct is objectively
  decidable open-book today (or one conjunct is decidably false, which settles the whole
  claim under "every part must hold") are excluded; the 13 surviving NEI claims each
  carry a genuinely unverifiable conjunct ("has a fan base", "is highly usable") and so
  measure honest abstention. Set size is now 48 (21 SUP / 14 REF / 13 NEI) — the
  textual-compoundness filter exhausts FEVER's test split, so PLAN's 60–80 target is
  not reachable without loosening the filter; the class imbalance is documented, agg
  reads per-label anyway. (The pre-screen `relay/down/feverc_008` trace is archived in
  `traces_archive/`.) Hub plan-compression got a prompt fix in the same pass:
  `ORCH_DECOMPOSE_SYS` now forbids settling facts from memory (every fact the answer
  depends on must appear in some sub-question; batching lookups is allowed).
- **dialogue · vanilla · feverc_001**: peer_A decomposed the claim and proposed REFUTES
  turn 1, peer_B ratified turn 2 — correct, `ratified=true`.

## Full 3×7 grid smoke (2026-07-07, every topology × arm on feverc_001 + fanout_002, ~$0.94 incl. probes)

All 42 cells ran with zero proxy errors and zero harness exceptions. `feverc_001`
(Westworld, REFUTES) scored **correct under all 21 topology×arm cells**. Mechanics
observed live: dialogue's contest path fired (dialogue·full·fanout_002: 1 contest,
proposal rejected), extract's observer pulled 6–19 beliefs per run across all three
topologies, full stored transcripts on handoff/report/message edges, sop counted
conformance, down parsed CONFIDENCE (1.0 → no challenge; a live challenge firing is
still unobserved — needs a low-confidence edge), board write-adoption stayed near zero
(1 write in 12 board/board_inert runs — measured, expected on short tasks).

Three defects found by the grid, all fixed + regression-tested:
1. **FanOutQA gold is a 2023-11-20 snapshot** — open-web agents answered TODAY's truth
   (all 21 fanout_002 runs "wrong": Ne Zha 2 is now in the top 5). Fix: `prep.py`
   prompt pins "answer as of 2023-11-20" (the paper's own convention). Validated live:
   hub picked the 2023 list post-pin and scored exact_match.
2. **`_match_list` false negatives** — gold `"J. J. Abrams"` missed answer "J.J. Abrams"
   (initials spacing) and compound gold items ("Anthony Russo and Joe Russo") never
   matched comma-separated answers. Fixed with two strictness-preserving relaxations;
   `tests/test_scoring_offline.py` holds the live examples as regressions.
3. **Think-rabbit-hole at commit points → guaranteed `no_answer`** — 2/14 hub runs died
   with the merge at `finish=='length'` (the whole output budget eaten inside `<think>`)
   and the constrained NO_FINAL_RETRY was *skipped* for truncated finishes. Since a
   length-death stores only the tiny proxy sentinel, the retry context is clean — all
   three topologies now retry once unless the finish was `ctx_overflow`.

Challenge suite live (vanilla): temporal inheritance **0/3** (both label probes rejected
the planted wrong belief; the NEI probe flipped to REFUTES = "other", an
abstention-calibration signal), spatial 3/3 correct incl. the SUPPORTS control.
Caveat for P4: with full B=8 successors simply re-verify, so vanilla may sit at a
rejection ceiling — consider a tighter `--budget` for the challenge cells.

## P0 result (relay · vanilla · smoke)

Calibration gate — *"budget B tuned so vanilla uses ≥2 shifts on ~70% of tasks"*: **met
(5/5 = 100% at B=8, K=3).** Hand-off notes are faithful (PDDL notes carry exact world
state + a next-step plan; GAIA notes summarize evidence and open threads). The 4-way
outcome axis fires across the slice (correct / wrong-confident / abstained). **Note-yield
after the wrap-up-spiral fix: GAIA 5/6 (83%), PDDL 2/2 (100%)** — every wrap-up finishes
`stop`; the one GAIA marker is a shift that truncated on an action turn before establishing
much. Scoreboard is regenerated by `agg.py`; see `traces/relay/vanilla/` and each run's
`handoff_notes.txt`.
