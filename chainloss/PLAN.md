# chainloss — does essential information die on MAS channels?

**Thesis.** At a FIXED total generation budget, accuracy on information-heavy tasks
falls as the length N of a relay (chain) MAS grows, because essential facts are lost
at the note-passing edges. Single-agent (N=1) vs MAS is therefore a *within-harness*
comparison: N=1 runs the exact same code path with zero edges.

**Lineage.** Harness forked from `multi-benchmark-eval:duet/harness/` (relay
topology only), stripped to hard vanilla — the AddOn seam, hub/dialogue topologies,
PDDL env, and all arm machinery are removed. Prompt hygiene rules and the
agent-loop robustness fixes (think-spiral wrap-up compaction, truncation sentinel,
context bounding) are inherited unchanged.

## Design

- **Manipulated variable:** N ∈ {1, 2, 4, 8} shifts. Only the number of channel
  crossings changes; every shift is a fresh context holding [task, inherited
  payload] and never a predecessor transcript (note arm).
- **Fixed budget:** `--budget` = total COMPLETION tokens for the whole run
  (default 32k; calibrated in the pilot against natural N=1 spend). Each shift gets
  an equal slice `B/N`. Every generated token bills the slice — solving, thinking
  (Qwen3.6 think trace counts as completion), and hand-off note writing. Channel
  overhead is honestly part of the cost of being a MAS.
- **Forced handoff, no early finish:** a non-terminal shift can NEVER end the run —
  its FINAL ANSWER line (if any) is ignored; at slice exhaustion (or a clean stop)
  it writes the hand-off note and the next shift starts. Only shift N commits.
  Rationale: early finish would let N=8 collapse to an effective N=2 and dilute
  the manipulation.
- **Constant channel width:** the note is capped (~300 words asked; hard clip at
  `NOTE_MAX_CHARS`). Width is constant across N; only the NUMBER of crossings varies.
- **Budget mechanics:** each slice reserves tail room for its mandatory terminal
  artifact (`NOTE_RESERVE` non-terminal / `COMMIT_RESERVE` terminal); the solve loop
  stops issuing calls when the work budget is spent, and per-call `max_tokens` is
  clipped to remaining so one runaway think cannot blow the slice. Small overruns
  from the 512-token wrap-up floor are possible and logged (`tokens_overrun`).

## Arms (the one control that makes the result interpretable)

| arm | edge payload | tests |
|---|---|---|
| `note` | free-prose hand-off note (capped) | the lossy channel (treatment) |
| `transcript` | cumulative rendered work logs of ALL prior shifts (assistant text + tool calls + clipped tool results; no CoT) | lossless channel, SAME N, SAME slices |

If `note` degrades with N while `transcript` stays flat → channel loss.
If both fall equally → budget fragmentation, thesis not supported. Caveats, logged
not hidden: `transcript` renders clip tool results (lossless up to clip + model ctx)
and pays no note-writing cost (bounded, reported per run).

## Benchmark

FanOutQA dev slice (width 3–6, prepped as in `multi-benchmark-eval:benchmarks/
fanoutqa/prep.py`, 2023-11-20 snapshot pin), `tool_profile=web`. Known risk from
duet P4: vanilla 28.8% all-or-nothing — floor, not ceiling. Mitigations:
- **Primary metric = fact recall** (fraction of gold list elements present in the
  final answer, same per-item matcher as the exact scorer) — graded, so the floor
  problem shrinks. Exact match kept as secondary.
- **Mechanism metric = fact survival**: post-hoc (`metrics/fact_survival.py`),
  P(gold fact appears in note_j | it was surfaced in shifts ≤ j) — information
  death observed directly on the channel, not inferred from accuracy.
- If the pilot shows notes trivially carry everything (channel never binds), we
  escalate info-load (popqa-compound, k-fact bundles) — decided on pilot data.

## Grid

Pilot (Claude, ≤$5): ~8–12 tasks × N{1,8} × both arms; calibrate `--budget` from
N=1 natural spend; check fact survival + note saturation.
Full grid (user runs): ~48 tasks × N{1,2,4,8} × {note, transcript}.

## Infra

Same stack as duet: shared Tinker proxy (`PROXY_URL`, default `127.0.0.1:8744`),
model tag `gpt-4o` → Qwen/Qwen3.6-35B-A3B, temp 0; Perplexity search API for
`web_search` (PERPLEXITY_API_KEY); conda env `autogen_gc`. Token/cost metering is
from response `usage` directly (no proxy-log dependency). Per-task USD safety cap $2.
