# AutoGen SelectorGroupChat — 28-task failure analysis (peer topology)

**Run:** 2026-06-15 · **Model:** `gpt-5.4-mini` (via local Perplexity proxy) ·
**Web backend:** Perplexity `/search` + plain-GET `fetch_url` (function tools, no
browser) · **Attempts:** 1 per task · **Per-task timeout:** 1800s ·
**Batch spend:** **$1.33** (28 tasks, `--parallel 4`).

**Task set:** the 28 hard GAIA tasks in `task_selection/autogen_gc_tasks.json`
(8×L1, 15×L2, 5×L3), **26/28 failed by the original Magentic-One run**, tagged by
the coordination they force: `web_compute` (14, two handoffs), `web_only` (12, one
handoff), `compute_only` (2, single-agent control).

**Method:** 28 parallel subagents, one per trace, each reading the full
`console_log.txt` **plus** the per-agent proxy wire-log (reconstructing what each
agent's model *privately saw* vs. what it *published* — the evidence needed to
detect MAST 2.4 distortion / 2.5 ignored-input across the publish bottleneck).
Judged from **two angles** — the MAST taxonomy **and** open-ended — with the
central task of separating *genuine inter-agent misalignment* from structural /
single-agent / harness causes. This mirrors the Magentic-One `FAILURE_ANALYSIS.md`
method exactly; it is **not** the formal LLM-as-judge pipeline — it is direct trace
reading. Per-trace detail in `FAILURE_ANALYSIS_verdicts.md`.

---

## Headline findings

1. **Genuine inter-agent misalignment is PRESENT here — and it was absent in
   Magentic-One.** 2/28 clean (`72c06643`, `48eb8242`) + 2/28 partial (`023e9d44`,
   `f0f46385`), with 4 more borderline. Magentic-One was **0/13 clean**. The peer
   round-table opened a failure channel the star structurally lacks. **This is the
   first positive evidence for the topology hypothesis.**

2. **The mechanism is exactly the one the design predicted: MAST 2.4 information
   distortion at the publish bottleneck.** In every clean/partial case the
   WebResearcher *privately retrieved the load-bearing fact* and then *dropped or
   distorted it in its single published digest*, so the Analyst/Verifier — who see
   only the digest — computed on a corrupted version they could not recover.

3. **All four genuine/partial cases are `web_compute`** — the partition-crossing
   category where information must travel WebResearcher → Analyst → Verifier.
   `web_only` produced 0 genuine cases (only routing/verification borderlines);
   `compute_only` produced 0. **Misalignment concentrates precisely where the
   handoff is.**

4. **But it is still a minority.** The dominant failures match Magentic-One:
   a broken verification layer (the Verifier rubber-stamps and finalizes on its
   first turn) and single-agent reasoning / retrieval / tool dead-ends. The new
   structural mode unique to this topology is **selector mis-routing** (the Analyst
   is never engaged on a compute task).

5. **The harness/normalizer hides far less here than in Magentic-One.** Substantive
   pass rate ≈ **11–12/28** vs **10/28** logged — the tool-less Verifier emitting a
   clean `FINAL ANSWER:` sentinel fixed most of the answer-envelope loss that cost
   Magentic ~3/13.

---

## Genuine-misalignment verdict distribution

| verdict | n | tasks |
|---|---|---|
| **yes** (clean inter-agent) | 2 | `72c06643`, `48eb8242` |
| **partial** | 2 | `023e9d44`, `f0f46385` |
| **borderline** | 4 | `e1fc63a2`, `3cef3a44`, `08cae58d`, `114d5fd0` |
| **no** | 20 | — |

By category (the key cut):

| category | yes | partial | borderline | no | n |
|---|:--:|:--:|:--:|:--:|:--:|
| `web_compute` (2 handoffs) | **2** | **2** | 1 | 9 | 14 |
| `web_only` (1 handoff) | 0 | 0 | 3 | 9 | 12 |
| `compute_only` (control) | 0 | 0 | 0 | 2 | 2 |

**Every genuine and partial case is in `web_compute`.** The single-agent control is
clean, as predicted.

---

## The genuine cases — 2.4 distortion across the publish bottleneck

These are the load-bearing result. In each, the fact existed *in-system*, in the
WebResearcher's private tool loop, and was lost at the moment it published.

**`72c06643` (L3, gas-law volume) — YES.** WebResearcher's private search returned
*"the water column above exerts a pressure of 1,086 bar … temperature at the bottom
is 1–4 °C"*. Its published digest reproduced the temperature and liquid-density
numbers but **silently dropped the pressure** — the one quantity needed to model
Freon-12 as a compressed gas (PV=nRT → 55 mL). Grep confirms `1,086`/`pressure`/
`bar` never appears in any downstream message. The Analyst computed on the
pressure-free digest → 226. The Verifier checked arithmetic *within the wrong
model* and never asked "does pressure matter at the bottom of the ocean?"

**`48eb8242` (L2, USGS crocodile records 2000–2020) — YES.** WebResearcher privately
held the full record table with each record's collection year (1988, 2009, 2011,
2012×2, 2014×2 …) — enough to filter to the date window. Its digest reported
*"seven Florida collection records"* as a **flat, year-blind count**, folding in the
1988 record that must be excluded. The Analyst, with no years to filter on, summed
`1 + 7 = 8`. The digest even admitted *"I could not safely total all records … by
year range,"* and neither peer pushed back.

**`023e9d44` (L2, CRV refund over a road trip) — PARTIAL.** WebResearcher's private
loop returned *"Cincinnati to Augusta is 1,023 miles by road"* plus per-state
mileage tables, then published a digest asserting both legs *"use the full"* highway
length (I-40 = 2,556 mi to Wilmington NC; I-90 = 3,099 mi Seattle→Boston) — a
geographically impossible premise. Partial rather than yes because the frame error
(highway-length vs trip-segment) is also a single-agent conflation; but the decisive
event is the correct segment distance vanishing at the publish step.

**`f0f46385` (L2, furthest ASEAN capitals) — PARTIAL.** A pairwise-distance compute
task. The selector **never engaged the Analyst**, so WebResearcher eyeballed the
furthest pair from raw coordinates and guessed wrong; its conclusion-only digest
*concealed that no computation had occurred*, and the Verifier rubber-stamped it.
Routing/verification misalignment rather than information loss — hence partial.

---

## MAST code frequency

| MAST code | category | # traces | read |
|---|---|:--:|---|
| 3.2 No/incomplete verification | 3 Verification | 16 | **dominant** |
| 3.1 Premature termination/finalize | 3 Verification | 16 | **dominant** |
| 1.x Flawed reasoning / task-interp | 1 Design | 13 | single-agent |
| 2.6 Reasoning-action mismatch | 2 Inter-agent | 4 | inputs-correct-calc-wrong |
| 3.3 Incorrect verification | 3 Verification | 4 | rubber-stamp |
| 2.4 Information distortion | 2 Inter-agent | **3** | **the genuine channel** |
| 2.3 Task derailment / loop | 2 Inter-agent | 3 | mostly degenerate loops |
| 2.5 Ignored other agent's input | 2 Inter-agent | 1 | weak/borderline |
| selector mis-route | (topology) | ~3 | new structural mode |

**Category 3 (verification) and Category 1 (single-agent) dominate, as in
Magentic-One.** But Category 2 — true inter-agent — *registers materially here*
(2.4×3, 2.6×4, 2.3×3) where in Magentic-One 2.4 was **0**. The peer topology moved
the needle on exactly the inter-agent axis.

---

## Cross-cutting structural patterns

**1. The publish bottleneck is a one-way lossy valve, and only `web_compute`
stresses it.** The WebResearcher is the *only* agent that ever holds rich evidence,
and it is *also* the only one that compresses that evidence into a digest. So when a
needed fact (pressure, per-record years, segment distance) doesn't survive the
compression, no downstream agent — and the tool-less Verifier *especially* — can
re-derive it. This is the topology-specific defect, and it fires precisely on the
tasks that force a fact across the WebResearcher→Analyst boundary.

**2. The Verifier rubber-stamps (cat-3, the single most common failure).** Its
system prompt mandates a PHASE-1 critical review — flag anything *"over-claimed
beyond what they actually showed,"* refuse to finalize on the same turn. In practice
it **finalized on its first turn in nearly every failing trace**, certifying
geographically impossible premises (`023e9d44`), un-computed answers (`f0f46385`),
year-blind counts (`48eb8242`), and give-ups (`08cae58d`, `114d5fd0`). The two-phase
design is sound but **prompt-level only** — the selector lets it finalize
immediately, so the intended adversarial check almost never executes. *Every
genuine/partial misalignment case would have been caught by a Verifier that actually
ran its review.*

**3. Selector mis-routing — a failure mode the star cannot have.** On compute tasks
the LLM selector repeatedly never engaged the Analyst (`f0f46385`, `e1fc63a2`,
`114d5fd0`), leaving arithmetic to the WebResearcher's head (off by ~400× in
`e1fc63a2`) or leaving an extractable PDF unparsed (`114d5fd0`, ~18 identical
WebResearcher give-up digests in a loop). Magentic-One's orchestrator has no
selector and no partition, so it has no analog.

**4. Single-agent retrieval / tool / modality dead-ends dominate the give-ups.**
`50f58759` (fetch_url returned nav chrome), `0b260a57` (source never located),
`676e5e31`/`f3917a3d` (K=8 tool-depth ceiling on deep-enumeration tasks),
`16d825ff`/`114d5fd0` (fetch_url cannot parse binary PDFs). These indict the tools
and the per-turn depth cap, not coordination.

**5. Refusal-to-commit.** Several traces had the facts but the WebResearcher/Verifier
chose *"cannot be determined"* over a best-supported answer (`08cae58d` had the
smoking-gun GAIA discussion and treated "the question is malformed" as a reason to
refuse rather than the key to the intended 2018). A Verifier that demanded a
best-effort commit would recover these.

---

## Substantive vs. logged scoring

| metric | count | tasks |
|---|---|---|
| **Strict exact-match (as logged)** | **10/28** | the 10 matched |
| **Substantively correct** | **≈11–12/28** | +`5a0c1adf`, +`5d0080cb`; `72e110e7` discounted |
| Genuinely wrong / no-answer | ≈16/28 | the rest |

Mis-scored **correct** (cheap recoverable wins, as in Magentic-One but far fewer):
- `5a0c1adf`: the digest correctly states **"Claus"** (gold), but the scorer pulled
  `final_answer` from a raw `web_search` tool-dump that leaked into the transcript —
  a **digest-leak parsing bug**, not a reasoning failure.
- `5d0080cb`: produced **`0.1777 m³`**, numerically identical to gold `0.1777`; the
  normalizer's unit suffix made it a false-negative.

Mis-scored the **other way** (a logged "win" that isn't genuine solving):
- `72e110e7`: `Guatemala` scored exact-match `true`, but it was lifted from a
  **leaked HuggingFace GAIA answer-key page** the search surfaced — **benchmark
  contamination**, not capability. (`5a0c1adf` surfaced the same kind of answer-key
  page.) A real scoring caveat for this set.

The two model-free fixes (accept a clean terminal value without the exact envelope;
unit-fold the normalizer) plus fixing the digest-leak would take logged 10 → ~12,
but the gap is small — this harness loses much less than Magentic-One's did.

---

## Implications for the project thesis

- **Magentic-One (star):** failures were single-agent (orchestrator) + broken
  verification + harness loss; genuine inter-agent misalignment ≈ 0/13.
- **AutoGen SelectorGroupChat (peer round-table):** the *same* structural backbone
  (broken verification, single-agent errors) **plus a real inter-agent channel** —
  2.4 information distortion across the publish bottleneck, 2/28 clean + 2/28
  partial, **concentrated entirely in the partition-crossing `web_compute` tasks**,
  with a new selector-routing failure mode on top.
- **Net:** swapping a star for a peer round-table with private sessions did **not**
  improve accuracy (10/28 ≈ Magentic's substantive rate) but **did manufacture the
  inter-agent misalignment the star suppressed** — exactly where theory predicts
  (the lossy private-state→digest compression). The capability-vs-structural axis
  now has a data point on the *structural-but-genuinely-inter-agent* quadrant that
  Magentic-One never reached.
- **Highest-value intervention:** enforce the Verifier's PHASE-1 review structurally
  (e.g. `GraphFlow` forcing a review-only first appearance) — it would catch every
  genuine 2.4 case here, because the distortion is visible to any agent that
  actually scrutinizes the digest against the question. The complementary fix is to
  let the digest carry its own evidence (or give the Verifier read-back of peers'
  tool outputs) so the publish bottleneck stops being a one-way valve.

---

*Artifacts: per-task runs under `reproduction/runs/autogen_gc/<uid8>/run_*/`
(`console_log.txt`, `result.json`); per-agent wire-logs from
`reproduction/proxy/raw_calls.jsonl` (tag `agc_<uid8>_run<n>`). Per-trace subagent
verdicts in `FAILURE_ANALYSIS_verdicts.md`. Produced 2026-06-15.*
