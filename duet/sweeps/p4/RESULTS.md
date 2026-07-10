# P4 full-grid results (2026-07-10)

**1,832/1,832 runs, $88.25, 0 unresolved failures.** Qwen3.6-35B-A3B via Tinker,
24 workers, benchmark-first phase order, sweep-scoped $100 cap (never hit).
Composition: 1,542 base grid + 150 GPQA completeness (sop/down/extract) + 140
challenge probes. Camera-ready accuracy table: `results_table.tex` / `.pdf`
(percent-only). Traces browsable in `duet/viewer/index.html` (rebuild with
`python duet/viewer/build.py`; serve the folder).

## 1. Headline: accuracy is flat across arms on every benchmark

Accuracy % (raw correct). FEVER relay at tool budget B=1; GAIA under an 8K output
cap; GPQA-D is the closed-book null anchor; `board_inert` is board's tool-use
control, headline FEVER cells only. Bold = per-column max.

| Family | Arm | relay FEVER n=48 | relay PDDL n=23 | relay GPQA-D n=50 | relay GAIA n=17 | hub FEVER n=48 | hub FanOutQA n=80 |
|---|---|---|---|---|---|---|---|
| Context | vanilla | 66.7 (32) | **52.2** (12) | 90.0 (45) | 17.6 (3) | 66.7 (32) | 28.8 (23) |
| | full | 64.6 (31) | **52.2** (12) | **94.0** (47) | **23.5** (4) | 68.8 (33) | 30.0 (24) |
| Protocol | sop | **70.8** (34) | **52.2** (12) | 84.0 (42) | 17.6 (3) | 68.8 (33) | 27.5 (22) |
| | down | 64.6 (31) | 47.8 (11) | 88.0 (44) | 17.6 (3) | 66.7 (32) | 27.5 (22) |
| State | board | 66.7 (32) | 47.8 (11) | 86.0 (43) | 17.6 (3) | **70.8** (34) | 28.8 (23) |
| | extract | 66.7 (32) | 47.8 (11) | 86.0 (43) | **23.5** (4) | 62.5 (30) | **33.8** (27) |
| | inert | 68.8 (33) | — | — | — | 66.7 (32) | — |

Statistics: paired sign tests vs vanilla, pooled over all cells — all p >= 0.50.
Per-cell spreads are <= ~1 binomial SD. On the GPQA null anchor the widest pair
(full vs sop, +6/−1 discordant) gives p = 0.125 — the most suggestive contrast in
the study, still n.s. **Arms differentiate on process axes, not outcome.**

## 2. Mechanism engagement (same runs, totals per cell)

| Arm | metric | FEVER rel | PDDL | GPQA-D | GAIA | FEVER hub | FanOutQA |
|---|---|---|---|---|---|---|---|
| full | transcripts inherited | 81 | 35 | 7 | 27 | 114 | 307 |
| sop | conformant / typed | 86/89 | 32/34 | 8/8 | 14/22 | 107/107 | 273/278 |
| down | challenges (declines) | 27 (38) | 23 (12) | 0 (5) | 12 (3) | 52 (56) | 210 (16) |
| board | beliefs written | 0 | 11 | 124 | 1 | 150 | 342 |
| extract | beliefs harvested (observer calls) | 337 (92) | 176 (36) | 42 (17) | 139 (30) | 400 (114) | 1258 (309) |

Key mechanism findings:

1. **Channel-competition adoption law** — board writes exactly where `add_belief`
   does not compete with a task tool (tool-less GPQA 124, hub workers 150/342)
   and ~never where it does (relay-fever 0, GAIA 1, PDDL 11). Tool-channel
   competition, not topology, is the variable.
2. **NEI overclaim is universal** (2 honest / 182 NEI cells) — calibration, not
   structure.
3. **extract harvests everywhere** (139–1,258/cell): observer-driven acquisition
   sidesteps board's adoption problem, confirming the acquisition-mode contrast.
4. **down engagement tracks task uncertainty** (fever 27 asks / 38 declines vs
   fanoutqa 210 / 16).
5. GAIA floor 18–24% under the 8K cap; board abstains 2x vanilla there
   (honesty-profile hypothesis, unread traces).
6. GPQA 90% closed-book is suspiciously high — spot-check pending.

## 3. SOTA edge (viewer "sota edge" panel)

Per column: best arm (ties broken State > Protocol > Context) and the tasks ONLY
it solved. Flatness shows up as near-total overlap — the winner's edge is 0–3
tasks per column:

- relay FEVER — sop: `feverc_012`
- relay PDDL — sop (3-way tie, identical solve sets): none
- relay GPQA-D — full: `gpqad_017`
- relay GAIA — extract (tie w/ full): `gaia_de9887f5`
- hub FEVER — board: none
- hub FanOutQA — extract: `fanout_006`, `fanout_012`, `fanout_013`

Caveat: `fanout_013` is likely scorer-margin (all arms answered near-identically);
`fanout_006` is a real factual difference. Near-miss review pending.

## 4. Challenge probes (P6: 140 runs, $3.68)

**Temporal** (authored wrong-belief hand-off note planted as relay initial_note,
12 probes x 7 arms at B=1; judge-free scoring: final==gold rejected /
==planted inherited):

- **Checkable falsehoods do not propagate, in any arm**: 7 of 8 SUPPORTS/REFUTES
  probes rejected by every arm — successors re-verify despite the note's "no
  further checking needed". Sole exception `chalT_001` (known noisy 4/7 unplanted
  baseline; inherited by 6/7 arms, board the only rejector — n=1 anecdote).
- **NEI probes: nobody ever abstains** (0 abstentions / 28 NEI probe runs); on
  chalT_010/011 every arm answered its natural overclaim direction AGAINST the
  plant. Inheritance and honesty separate cleanly: the relay resists planted
  falsehood, but honest-NEI is a universal calibration failure (finding 2 above).
- Per-arm inheritance 1–3 of 12 (board 1, full 3 — plausible since full carries
  the note verbatim — all within noise at n=12).
- Plant directions: chalT_009/010/011 flipped to REFUTES (9205ae40) after
  unplanted baselines showed the default SUPPORTS plant was confounded with
  natural overclaim. `down`'s cell measures downstream challenge only (no
  producer to challenge for the planted note itself).

**Spatial** (same-name entity-collision conjunctions, 8 probes x 7 arms, hub):
**ceiling** — 8/8 for vanilla/full/down/board/extract, 7/8 inert, 6/8 sop.
Entity collisions do not fool decompose->merge at this difficulty; clean null.

Rerun the cross-tab anytime: `python duet/challenge/analyze.py`
(latest-run-per-task only).

## 5. Ops journal

- Sweep runner: `harness/run_sweep.py` (phases as barriers, resume via
  `jobs_done.jsonl` + persistent t0, cost metered from proxy calls.jsonl with
  ts>=t0 AND duet_ tag prefix — prior spend in the same logs never counted).
- Session-cleanup killed harness-tracked runs twice -> detached relaunch via
  `start_new_session`; resume paid nothing twice.
- PDDL: all 138 jobs import-crashed (pddlgym only in camel_pddl env) -> PY_FOR_SPEC
  map; $0 lost.
- `gpqad_031` hung ~1h (upstream call in-flight 14+ min; agent.py sets no client
  timeout — hardening TODO). SIGTERM -> built-in retry recovered cleanly.
- Challenge jobs logged `outcome=? $0.000` cosmetically (newest_outcome used the
  task-file spec as the bench dir name) — fixed post-hoc in run_sweep.py; runs,
  traces, and metering were unaffected.

## Pending

- Manual (Claude-assisted) near-miss review: fanout_013, GPQA closed-book
  spot-check, GAIA board honesty-profile traces.
- Process judges still need hand-label validation before citing judge numbers.
