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

Calibration pilot (cap 4500 tokens/agent, none-arm): capped solo 2/10 solved vs
capped 3-hop chain 7/10 (independent-retry expectation from the solo rate ≈ 49%)
→ the channel is load-bearing at this cap. Gate PASSED; grid run at cap 4500.

### Grid — 3 arms × 39 tasks × k=3 (351 relays, tag `br_g2c4500`, 2026-07-30)

| arm | n | accuracy | Wilson 95% CI |
|---|---|---|---|
| none (filler) | 117 | **0.632** | [0.542, 0.714] |
| homo (shared belief set) | 117 | **0.701** | [0.613, 0.776] |
| probe (different belief sets) | 117 | **0.709** | [0.622, 0.784] |

Paired per-task deltas (39 tasks): homo−none **+0.068** (SE 0.048), probe−none
**+0.077** (SE 0.045, p≈0.09), probe−homo **+0.009** (SE 0.055). **All ns at
~95%.** The headline contrast — heterogeneous vs shared beliefs (probe−homo) —
is a dead null in both regimes.

### Findings

1. **Ceiling removed, still no heterogeneity effect.** v2 has real headroom
   (63–71% on a 39% pool, ~4× v1's error mass), the channel is provably
   load-bearing, and probe−homo is +0.9pp (SE 5.5pp). Belief heterogeneity
   across the relay does not measurably change end-task accuracy.
2. **The belief-vs-none trend (+7pp, ns) is mostly a muteness artifact, not
   belief transmission.** 42% of agent turns hit the cap mid-think and emit the
   empty-channel placeholder. Final-agent muteness (auto-wrong) differs by arm:
   none 36/117, probe 30/117, homo 24/117 — that gap alone accounts for most of
   the arm deltas. Conditional on a non-mute final agent, accuracies are
   ~88–95% across arms with no clean ordering. Plausible mechanism: any extra
   system-prompt text about *how to work* nudges the model to think less before
   writing; nothing suggests belief *content* traveled the channel and helped.
3. Sign flip vs v1 (beliefs slightly negative → slightly positive) at ~1–2 SE
   in both directions is exactly what noise around zero looks like.

### Verdict (v1 + v2)

Across an uncapped relay (v1) and a budget-capped handoff relay where the
channel demonstrably carries the solution (v2), injecting subjective,
task-adjacent beliefs — same or different per agent — produced **no
statistically detectable effect on end-task accuracy** (351 relays per regime,
paired SEs ~2–5pp). Whatever these beliefs do, they stay cheap: they neither
poison nor power the relay on MATH-L5. Caveats: convergent-answer benchmark
(near-worst-case for belief effects), deliberately non-essential beliefs by
design, one model, k=3.

## Spend

v1 (screen + discarded screen + top-up + smoke + grid): **$10.33**.
Total incl. v2 (pilot + capped grid): **$13.55** of the $20 cap,
self-metered from proxy calls.jsonl.
