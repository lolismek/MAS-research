# Magentic-One — 13-task failure analysis (de-Bing'd, real search API)

**Run:** 2026-06-15 · **Model:** `gpt-5.4-mini` (via local Perplexity proxy) ·
**Search backend:** Perplexity `/search` → clean local SERP (no Bing, no CAPTCHA,
verified 0 Bing landings across all 13) · **Attempts:** 1 per task ·
**Per-task timeout:** 1200s · **Batch spend:** **$2.26** (hard guard $4.50).

**Task set:** the 13 attachment-free GAIA tasks from the MAST `MagenticOne_GAIA`
traces (8×L1, 4×L2, 1×L3). The 2 attachment tasks (1 audio, 1 PDF) were excluded.
This subset is **failure-biased**: only 2/13 succeeded under the original GPT-4o
Magentic-One run, so beating 2/13 is the bar.

**Method:** 13 parallel subagents, one per trace, each reading the full
`console_log.txt` **plus** the proxy wire-log digest (the orchestrator's hidden
Task-Ledger / Progress-Ledger JSON that never reaches the console). Judged
multi-dimensionally against the MAST taxonomy **and** open-ended, with the central
task of separating *genuine inter-agent misalignment* from structural causes.
This is **not** the formal LLM-as-judge pipeline — it is direct trace reading.

---

## Headline findings

1. **Genuine inter-agent misalignment is essentially absent.** 0/13 clean cases;
   2/13 borderline (orchestrator disregarded a correct WebSurfer finding — but
   that is hub control-policy, not capable agents miscommunicating). No
   information-withholding (2.4), no conversation reset (2.1), no spoke ignoring
   the hub. **This overturns the earlier "Magentic fails by 2.5-type misbehavior"
   read.**

2. **The real failures are structural / single-agent**, concentrated in the
   orchestrator (which does the reading + reasoning + self-grading itself) and in
   a broken verification/termination layer.

3. **The true substantive pass rate is ~4–5/13, not 1/13.** A third of the
   "failures" are correct answers discarded by the harness/normalizer.

---

## Strict vs. substantive scoring

| metric | count | tasks |
|---|---|---|
| **Strict exact-match (as logged)** | **1/13** | `0383a3ee` |
| **Substantively correct** (right answer reached) | **4–5/13** | `0383a3ee`, `27d5d136`, `5d0080cb`, `023e9d44`, (`5a0c1adf` ~) |
| Genuinely wrong answer | 8/13 | `3cef3a44`, `3f57289b`, `72e110e7`, `7673d772`, `04a04a9b`, `05407167`, `08cae58d`, `00d579ea` |

The gap between strict (1) and substantive (~4–5) is the single most actionable
result: harness/normalizer artifacts, not the model, account for it.

---

## Per-trace results

| # | task | L | logged | substantive | dominant root cause | MAST codes | genuine 2.x misalignment? |
|---|------|---|--------|:---:|------|------|:---:|
| 1 | `0383a3ee` | 1 | ✅ correct | ✅ | clean control — one search + one confirm | none | no |
| 2 | `27d5d136` | 1 | ❌ | ✅ | **grading**: LaTeX vs Unicode (same formula) | (3.2 benign) | no |
| 3 | `5d0080cb` | 1 | ⚪ none | ✅ | **harness**: `0.1777` emitted w/o `FINAL ANSWER:` envelope | 3.1, 1.1 | no |
| 4 | `023e9d44` | 2 | ⚪ none | ✅ | **harness**: `8` emitted at turn-cap, not recognized; over-literal I-90 loop | 1.3, 1.5, 3.3, (2.5) | borderline |
| 5 | `5a0c1adf` | 1 | ⚪ none | ~✅ "Claus" | over-strict verify loop + env drift (E.Germany→Germany) + budget | 1.3, 1.5, 3.2, 3.3, 3.1 | no |
| 6 | `3f57289b` | 1 | ❌ 589/519 | ❌ | **orchestrator misread the stats table** (correct row on page) | 3.2, 3.3, 1.1 | no |
| 7 | `7673d772` | 1 | ❌ | ❌ | **orchestrator mis-alphabetized index** → wrong section, then fabricated | 2.3, 1.3, 1.5, 3.1, 3.2, 2.6 | no |
| 8 | `08cae58d` | 2 | ❌ 1987/2018 | ❌ | **orchestrator misread the spec** (Google-Finance split semantics) + browser couldn't fetch data | 1.1, 1.3, 2.6, 3.1, 3.3 | no |
| 9 | `04a04a9b` | 2 | ❌ 0/41 | ❌ | **statistical-reasoning failure** (never did 1037×0.04); fact-sheet pre-biased "0" | 1.1, 2.6, 3.2, 3.3 | no |
| 10 | `3cef3a44` | 1 | ❌ | ❌ | Assistant mis-categorized (dropped "fresh basil"); skipped planned verification | 3.2, 1.1, 2.6 | no |
| 11 | `72e110e7` | 1 | ❌ Nepal | ❌ | **tool/env dead-end** (BASE page renders blank) + SEO-spam poisoned context | 1.3, 1.5, 2.6, 3.2, 3.3 | no |
| 12 | `05407167` | 2 | ❌ | ❌ | orchestrator plan-narration loop; never opened the known-correct URL | 1.3, 1.5, 2.5, 3.2, 3.3, 2.3 | partial |
| 13 | `00d579ea` | 3 | ❌ | ❌ | **modality wall** (can't transcribe video) + asymmetric trust on weak text | 3.2, 3.3, 1.3, 1.5, 1.1 | no |

Legend: ✅ correct · ❌ wrong · ⚪ no answer emitted · ~ partially/substantively right

---

## MAST code frequency (how often each failure mode appears)

| MAST code | category | # traces | read |
|---|---|:---:|---|
| 3.2 No/incomplete verification | 3 Verification | ~8 | **dominant** |
| 3.3 Incorrect verification | 3 Verification | ~7 | **dominant** |
| 1.3 Step repetition | 1 Design | 7 | loops |
| 1.5 Unaware of stopping conditions | 1 Design | ~6 | loops |
| 2.6 Reasoning-action mismatch (intra-hub) | 2 | ~5 | plan≠dispatch |
| 1.1 Disobey task specification | 1 Design | ~5 | mostly spec misread |
| 3.1 Premature termination | 3 | ~4 | budget/format |
| 2.5 Ignored other agent's input | 2 Inter-agent | 2 | borderline only |
| 2.3 Task derailment | 2 Inter-agent | ~2 | downstream of hub error |
| 2.1 / 2.2 / 2.4 | 2 Inter-agent | **0** | not observed |

**Category 3 (verification) and Category 1 (loop/stopping) dominate. Category 2
(true inter-agent misalignment) barely registers** — and where it does (2.5×2,
2.3×2) it is downstream of a hub-level error, not capable agents miscommunicating.

---

## Cross-cutting structural patterns

**1. The orchestrator is a single point of failure that does the reasoning itself.**
In hub-and-spoke, the orchestrator reads the data, reasons, and self-grades. So
*its* individual slips become whole-task failures with no agent positioned to
catch them:
- `3f57289b`: the correct row (`Roy White … 75 BB … 519 AB`) was on the page; the
  orchestrator scanned the walks column wrong and picked Nettles (68 → 589).
- `7673d772`: read the LII index's display order as alphabetical → anchored on the
  wrong rules section for 50 turns.
- `08cae58d`: read "according to Google Finance, without adjusting for split" as
  "hunt raw pre-split prices" → wrong sub-goal.
- `04a04a9b`: never computed `1037 × 0.04 ≈ 41`; the fact-sheet had pre-committed
  to "the answer is 0".

**2. Verification is broken (cat-3, ~9/13).** Answers are emitted with no real
check — frequently while the orchestrator's *own ledger* says "unverified / do not
use as default" and then ships it anyway:
> `72e110e7` ledger call 56: *"do not reuse Nepal as a default answer"* →
> call 57: *"FINAL ANSWER: Nepal"*.

**3. Loop detection is decoupled from control.** The orchestrator repeatedly sets
`is_in_loop: true` and then re-issues the **same** instruction (`5a0c1adf`,
`72e110e7`, `7673d772`, `023e9d44`, `05407167`, `08cae58d`, `00d579ea`). It can
name the loop but cannot break it — a concrete Progress-Ledger design defect.

**4. Forced confident guess at budget exhaustion.** Out of turns, the orchestrator
fabricates a specific wrong answer instead of abstaining (`Nepal`, `titleholders`,
`1987`) — converting an honest "no answer" into a confident miss.

**5. Reasoning-action mismatch in speaker selection (intra-hub 2.6).** Plans name
`ComputerTerminal` / `FileSurfer` to recover, but the orchestrator never dispatches
them — always re-selects `WebSurfer` (`72e110e7`, `05407167`).

**6. Tool / modality dead-ends** account for the genuinely-unsolvable cases:
`72e110e7` (a JS page renders blank in the harness), `08cae58d` (un-fetchable 1987
prices), `00d579ea` L3 (YouTube audio/video cannot be transcribed by the WebSurfer).

---

## The harness/normalizer is hiding correct answers (the cheap win)

Four traces produced the **substantively correct answer** that scoring threw away:

| task | what the system actually produced | why it scored wrong |
|---|---|---|
| `27d5d136` | `(\neg A \to B) \leftrightarrow (A \lor \neg B)` | LaTeX vs gold's Unicode `(¬A → B) ↔ (A ∨ ¬B)` — identical formula |
| `5d0080cb` | `0.1777` (matches gold exactly) | emitted as a bare orchestrator line, no `FINAL ANSWER:` envelope |
| `023e9d44` | `8` (matches gold exactly) | emitted on the turn-cap turn, never recognized as the final answer |
| `5a0c1adf` | reached "Claus" (gold) | over-strict verify loop burned the budget before finalizing |

**Two cheap, model-free fixes**:
1. **Answer capture** — accept the orchestrator's terminal value even without the
   exact `FINAL ANSWER:` prefix (recovers `5d0080cb`, `023e9d44`, likely `5a0c1adf`).
2. **Normalizer** — unicode-fold LaTeX/symbols and handle name-subset matches
   (recovers `27d5d136`).

These would take the measured rate from **1/13 → ~4–5/13** with **zero** change to
the model or agents. Only *after* that do the residual genuine failures — the
verification epidemic and the loop-no-break defect (Layer B) — become the real
target.

---

## Implications for the project thesis

- The de-Bing experiment already showed fail-rate **held** after removing the
  search confound → failures weren't the Bing harness.
- This trace-level read shows they **also aren't inter-agent misalignment.** They
  are (a) single-agent reasoning errors localized in the orchestrator, (b) a
  systematically broken verification/termination layer, (c) loop-detection that
  doesn't intervene, (d) tool/modality dead-ends, and (e) a large dose of pure
  harness/normalizer loss.
- Net: on this subset, "multi-agent coordination" is **not** where Magentic-One
  breaks. The capability-vs-structural axis lands almost entirely on the
  structural/single-agent side, with the orchestrator's verification policy as the
  highest-value place to intervene.

---

*Artifacts: per-task runs under `reproduction/runs/magentic/<uid8>/run_*/`
(`console_log.txt`, `result.json`); wire-log digests were built from
`reproduction/proxy/raw_calls.jsonl`. Batch driver + per-trace subagent verdicts
were produced 2026-06-15.*
