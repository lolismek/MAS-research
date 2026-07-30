# beliefrelay — results

Question: does belief heterogeneity across relay agents change end-task accuracy?
Design details in README.md. Model: Qwen/Qwen3.6-35B-A3B (Tinker), temp 0.7,
16k output cap per call. Pool: 39 MATH-L5 tasks, single-agent solve rate 0.391
(band 0–50%, every task with ≥1 completed screen sample). Beliefs: 3 sets × 3
per task, Claude-authored answer-blind, leakage check PASS.

## v1 — uncapped relay (each agent has budget to solve alone)

3 arms × 39 tasks × k=3 (one benign duplicate record; 2026-07-30, run tag `br_grid`).

| arm | n | accuracy | Wilson 95% CI |
|---|---|---|---|
| none (filler) | 117 | **0.940** | [0.882, 0.971] |
| homo (shared belief set) | 117 | **0.932** | [0.871, 0.965] |
| probe (different belief sets) | 118 | **0.924** | [0.861, 0.959] |

Paired per-task deltas (39 tasks): homo−none −0.009 (SE 0.026), probe−none −0.011
(SE 0.016), probe−homo −0.002 (SE 0.024). **All null at ~95%.**

### Findings

1. **No detectable accuracy effect of belief injection or heterogeneity** in an
   uncapped relay. Point ordering (none > homo > probe) hints at a sub-noise cost
   of belief text, but SEs swamp it.
2. **Ceiling artifact, structural not incidental:** the relay lifts a 39%
   single-agent pool to ~93–94% (+54pp). With a 16k budget each agent simply
   re-solves the problem; hop 2/3 act as independent retries + verification
   (pass@3-with-checking). Nothing forces information — beliefs included —
   to matter across the channel.
3. Truncation hygiene held: 40/1056 agent turns hit the cap (~4%), uniform
   across arms.

### Method notes registered for posterity

- 9k-cap screen artifact: a mid-think truncation yields a placeholder (proxy
  strips unterminated `<think>`), scoring auto-wrong. First screen measured
  budget-verbosity, not difficulty; discarded, rerun at 16k.
- Pool integrity rule: tasks whose screen samples ALL died at the cap are
  budget-bound, not hard → excluded (24/26 of the original 0-raters).

## v2 — budget-capped handoff relay (forced division of labor)

Motivation: v1's ceiling shows the relay never needed its channel. v2 caps each
agent's output (thinking included) below a solo solve (~4–5k vs the ~8–16k the
model wants), with handoff-explicit prompts (stop reasoning early, externalize
partial progress, last agent must answer). Calibration gate: capped solo agent
rare-solves; capped 3-hop chain solves substantially more often — that window is
where the channel is load-bearing and belief effects have room to act.

Status: pilot + grid in progress (results appended below when complete).

## Spend

v1 total (screen + discarded screen + top-up + smoke + grid): **$10.33** of the
$20 cap, self-metered from proxy calls.jsonl.
