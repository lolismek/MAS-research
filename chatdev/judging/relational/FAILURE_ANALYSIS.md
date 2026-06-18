# ChatDev — 15-task re-judging under a broad inter-agent-misalignment lens

**Re-judged:** 2026-06-18 · **Traces:** the **15 regenerated** ProgramDev runs
(`gpt-5.4-mini`, native ChatDev v1.1.6, post-confound-fix; `../../traces/`) · **This
is a fresh read of regenerated traces, not a re-read of the old ones** (the prior
`gpt-5.4-mini` traces were lost; the formal `gpt-5.5` MAST judge in `../judged/` ran
on those lost traces and is stale).

This is the ChatDev counterpart to the Magentic-One broad-lens pass
(`../../../magentic_one/judging/relational/`). Same method — one dedicated subagent
per trace, direct reading of the dialogue log *and the produced code*, three angles
at once (MAST codes · open-ended pinpoint · broad relational reading) — adapted to
ChatDev's topology: a **sequential waterfall of paired role-play dialogues over a
shared code store**, not Magentic's hub-and-spoke. Rubric: `GUIDELINES.md`.
Per-trace detail: `FAILURE_ANALYSIS_verdicts.md`.

The broad question, per the project lead: did the agents fail to **understand,
trust, or communicate with each other** — theory-of-mind gaps, miscalibrated trust
(too suspicious / too credulous), dropped or withheld context? Not only the narrow
"did a capable agent distort/withhold a correct value on a hand-off?" (MAST 2.4/2.5).

---

## Headline reframe

1. **The stale "ChatDev withholds information in 15/15 runs" finding does not
   survive.** The prior summary (`../judged/summary.md`) reported MAST **2.4
   Information Withholding in 15/15** and **2.5 Ignored Input in 15/15** — an
   architecture-signature claim ("the code-store channel loses artifacts in every
   run, including the working controls"). Under this pass — regenerated traces with
   the completion-truncation confound fixed, read with the markdown-mangling
   artifact excluded — **2.4 and 2.5 both drop to 0/15** (1 borderline). Most of
   the old signal was the artifact, not the architecture: gpt-5.4-mini's verbose
   completions were truncated mid-line by ChatDev's `max_tokens = 4096 − prompt`
   budget, and ChatDev's logger mangled the code shown in its state-dump tables —
   both read by the earlier LLM-judge as code "lost between agents." Remove the
   truncation (proxy fix) and stop scoring the mangled tables, and the
   inter-agent-withholding channel that looked universal **disappears**.

2. **Under the broad lens, material inter-agent misalignment is rare: 1/15.** Only
   `TheCrossword` shows *material* (moderate) misalignment. Five traces show *weak*
   strands; nine are *none*. **Zero strong.** This is the near-inverse of the
   Magentic-One pass (8/13 material). The difference is topological, not
   evaluative — see "What changes for the thesis."

3. **ChatDev's paired channels mostly coordinate *well*.** The dominant observed
   pattern is the *opposite* of a breakdown: across the batch the Code
   Reviewer↔Programmer and Tester↔Programmer dialogues repeatedly **catch a real
   bug, communicate it precisely, and the Programmer applies the fix** (Pong's
   double-scoring serve bug, ConnectFour's missing-GUI startup crash, Checkers'
   stubbed GUI, Wordle's empty word-list, DouDizhuPoker's three rule bugs, the
   Sudoku uniqueness defect). The delivered software works in **13/15** runs — up
   from **3/15** in the original GPT-4o human-annotated runs. A stronger coder model
   plus an un-truncated channel turns ChatDev's review/test loop into a mostly
   functional collaboration.

4. **The one genuine relational failure is a *fabricated hand-off*, not a dropped
   one.** In `TheCrossword`, the Tester reports the exact blocking bug ("Clue
   5-across goes out of bounds at (2,7)"); the Programmer's final modification
   *adds a docstring claiming it moved the clue to fit* while leaving the
   coordinate `(2, 5)` unchanged — a narrated fix that was never performed (verified
   in the shipped `puzzle.py`: L102 claims the move, L120 keeps `BEE` at `(2,5)`).
   The correct in-system report was effectively nullified by a teammate
   misrepresenting its own work (MAST 2.6), and the fixed-cap test loop accepted it.
   That is the whole of ChatDev's material misalignment in this batch.

---

## Strength distribution (broad lens)

| strength | # | traces |
|---|---|---|
| **strong** | 0 | — |
| **moderate** | 1 | `TheCrossword` |
| weak | 5 | `StrandsNYT`, `Checkers`, `Gomoku`, `CandyCrush`, `Wordle` |
| none | 9 | `ConnectionsNYT`, `DouDizhuPoker`, `MonopolyGo`, `Sudoku`, `TicTacToe`, `TextBasedSpaceInvaders`, `ConnectFour`, `Pong`, `TinyRouge` |

The five **weak** cases are technically-present-but-non-decisive strands: a
store-channel drop that the *next review cycle caught and fixed* (`Checkers`,
`Gomoku`), a harness `_tkinter` loop mistaken for friction (`CandyCrush`), a
single-agent capability failure with a positive review channel (`StrandsNYT`), and
a soft-spec fix that worked (`Wordle`). None changed the outcome.

---

## Narrow vs. broad, per trace

| trace | outcome (delivered SW) | MAST codes | strict 2.4/2.5 | **broad misalignment** | locus |
|---|---|---|:---:|:---:|---|
| `TheCrossword` | **wrong** (crashes on startup) | 1.1, 2.6, 3.1, 3.2, 3.3 | borderline | **moderate** | within-phase |
| `StrandsNYT` | **wrong** (crashes on startup) | 1.1, 3.2, 3.3 | NO | weak | single-agent |
| `Checkers` | works | 3.2 | NO | weak | store-channel |
| `Gomoku` | works (control) | 3.2 | NO | weak | store-channel |
| `CandyCrush` | works | 1.3, 1.5, 3.2 | NO | weak | harness-artifact |
| `Wordle` | works | 3.2 | NO | weak | within-phase |
| `ConnectionsNYT` | works | 3.2 | NO | none | within-phase |
| `DouDizhuPoker` | works | 3.2 | NO | none | within-phase |
| `MonopolyGo` | works | 3.2 | NO | none | within-phase |
| `Sudoku` | works | 3.3 | NO | none | within-phase |
| `TicTacToe` | works | 1.3, 2.6, 3.2 | NO | none | within-phase |
| `TextBasedSpaceInvaders` | works | 3.2 | NO | none | within-phase |
| `ConnectFour` | works (control) | — | NO | none | within-phase |
| `Pong` | works (control) | — | NO | none | within-phase |
| `TinyRouge` | works | — | NO | none | within-phase |

MAST mode frequencies (n=15, this pass): **3.2** weak-verification = 10 · **3.3**
no/incorrect-verification = 3 · **1.1** disobey-spec = 2 · **1.3** step-repetition =
2 · **2.6** action-reasoning-mismatch = 2 · **1.5** = 1 · **3.1** = 1 · **2.4 = 0 ·
2.5 = 0** · (2.1/2.2/2.3/1.2/1.4 = 0). Compare the stale pre-fix numbers (2.4 = 15,
2.5 = 15, 3.1/3.2/3.3 = 13/13/13): the verification codes stay common, but the
inter-agent (2.x) codes collapse.

---

## Recurring shapes (described, not codified — we already have MAST)

**A. Working coordination is the norm — the review/test channel does its job.**
The most common thing that happens between two ChatDev agents in this batch is a
*successful* exchange: the Reviewer or Tester names a real, specific defect and the
Programmer fixes it. This is the inverse of Magentic's "delivered but ignored." It
is worth stating as a positive finding: with truncation removed and a capable coder,
ChatDev's paired dialogues are mostly aligned. (`Pong`, `ConnectFour`,
`DouDizhuPoker`, `MonopolyGo`, `ConnectionsNYT`, `Sudoku`, `Wordle`.)

**B. The shared code store can drop content — but review usually self-corrects it.**
ChatDev's distinctive failure surface (the store as the only inter-phase memory) did
fire twice: the Coding phase's GUI body was reduced to a stub in the store
(`Checkers`, `Gomoku`). In *both* cases the very next CodeReview cycle caught the
gap and the Programmer restored it, so it never reached the user. The channel is
lossy but, when review runs, self-healing — which is exactly why these are *weak*,
not material. (This is the residue of the stale "2.4 in every run" claim: a real
mechanism, mostly neutralized by the review loop once truncation no longer amplifies
it.)

**C. The single genuine relational break is over-credulous acceptance of a
fabricated fix.** `TheCrossword`: a correct Tester report → a Programmer that
*claims* the fix in prose while leaving the code unchanged → a fixed-cap test loop
that accepts the claim without re-running. Trust miscalibration (the loop believed a
teammate's self-report over a check it had just run) layered on an action-reasoning
mismatch. The root cause underneath is single-agent (the Programmer cannot do the
grid arithmetic), which is why it is moderate, not strong.

**D. Most "weak verification" (3.2) here is a *harness* limit, not a trust
breakdown.** The test phase runs under a Tk-less Python, so GUI games "pass" by
exiting gracefully on a missing-`_tkinter` import without ever exercising gameplay.
That is a real verification gap (hence 3.2 is common), but it is a structural
property of the test sandbox, not two agents who saw contradicting evidence and
mis-trusted each other — so it almost never rises to relational. The rubric's bar
("over-credulity counts only when the agent had concrete in-dialogue reason to
distrust what it approved") keeps these out of the misalignment column. The one
trace that clears that bar is `TheCrossword`.

---

## What stays true / what changes

- **The verification weakness is real and survives.** Cat-3 codes (3.2/3.3) remain
  the most common MAST findings (10/15 carry 3.2). ChatDev's review/test phases are
  shallow — they pass on a headless smoke run and rarely exercise actual gameplay.
  This is genuine and unchanged from the prior reading; what changes is that it is
  mostly a *verification-design / harness* property, not an *inter-agent* one.
- **The inter-agent (2.x) signature was largely an artifact.** The clean, defensible
  version of the prior thesis is **not** "ChatDev's communication channel loses
  information in every run." It is narrower and more honest: *the shared code store
  can drop content, but the review loop usually catches it; once the
  completion-truncation confound is removed, genuine inter-agent misalignment is
  rare (1/15) and never spoke-distorts-upward in kind.*
- **For the capability-vs-structural thesis:** ChatDev's failures in this batch are
  overwhelmingly **single-agent capability** ceilings (StrandsNYT's exact-cover
  board; TheCrossword's grid arithmetic) and **verification-design** limits, not
  coordination breakdowns. The relational component the Magentic pass surfaced as
  *pervasive* is, in ChatDev, *nearly absent*.

## What changes for the cross-system (topology) comparison

This is the sharp contrast that makes the two systems worth studying together:

- **Magentic-One (hub-and-spoke):** broad-lens material misalignment **8/13**, every
  instance **hub→spoke** — the orchestrator mis-modeling, mis-trusting, or
  under-informing its spokes. The coordination burden sits entirely on the hub, and
  so does every failure.
- **ChatDev (waterfall + shared store):** broad-lens material misalignment **1/15**.
  Coordination is distributed across short, paired, single-purpose dialogues with a
  persistent shared artifact between them, and a built-in review/test loop whose job
  *is* to catch defects. That structure makes most hand-offs succeed and makes the
  lossy store mostly self-correcting. The misalignment that does occur is
  within-phase (a Programmer misrepresenting its own work), not a cross-phase
  distortion.

The claim is therefore **not** "ChatDev coordinates better than Magentic" in the
abstract — it is that **the two topologies fail in different places**: Magentic's
single coordinator is a concentrated point of relational failure; ChatDev's
review-gated pipeline diffuses and largely repairs coordination errors, leaving
*single-agent capability* and *shallow verification* as its dominant failure modes.
That is the contrast the peer-topology baseline (AutoGen GroupChat) is positioned to
complete.

---

## Method

15 per-trace subagents, one per trace, each reading the run's dialogue log
(`warehouse/*_DefaultOrganization_*.log`, the public transcript) **and the produced
`.py` files** (several executed or parsed the code to confirm the outcome), judged
against `GUIDELINES.md` on three angles (MAST · open-ended pinpoint · broad
misalignment). Every claim is grounded in log line numbers and/or code. This is
direct trace reading, not an LLM-as-judge pipeline. Per the rubric, the now-fixed
completion-truncation is treated as resolved (incompleteness = genuine behavior),
the markdown-mangled state-dump tables are excluded as a logging artifact, and the
two non-working deliverables (`TheCrossword`, `StrandsNYT`) had their crashes
reproduced. The four load-bearing verdicts (the one material finding, the two
non-working traces, and the "regenerated run fixed the original's soft failure"
claims) were independently spot-checked against the shipped code.

*Artifacts: `FAILURE_ANALYSIS_verdicts.md` (per-trace), `GUIDELINES.md` (rubric),
`verdicts/` (raw per-trace subagent outputs). Strict-lens counterpart: the formal
`gpt-5.5` MAST judge in `../judge/` + `../judged/` — currently **stale** (ran on the
lost traces); re-running it on these regenerated traces would complete the
strict-vs-broad pairing.*
