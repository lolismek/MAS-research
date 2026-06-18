# Cross-system comparison — broad-lens inter-agent misalignment

Side-by-side of the **broad-lens relational re-judging** (2026-06-18) of the two
MAS that have a matching `judging/relational/` pass:
**Magentic-One** (`magentic_one/judging/relational/`) and
**ChatDev** (`chatdev/judging/relational/`). Same method on both — one dedicated
subagent per trace, direct reading of the dialogue (and, for ChatDev, the produced
code), three angles at once (MAST codes · open-ended pinpoint · broad relational
reading) — adapted to each topology.

**Broad lens** (per the project lead): did the agents fail to *understand, trust, or
communicate with each other* — theory-of-mind gaps, miscalibrated trust (too
suspicious / too credulous), dropped or withheld context — not only the narrow MAST
"a capable agent distorted/withheld a correct value on a hand-off" (2.4/2.5).

## A note on "acceptance / failure"

The two systems are scored on different success criteria, so the pass/fail column is
**not strictly parallel** — read each in its own terms:

- **ChatDev** → *delivered software runs* (pass) vs *crashes / broken* (fail).
- **Magentic-One** → *GAIA answer is exact-match correct* (pass) vs *wrong / no-answer* (fail).

**Misalignment? = yes** means any non-zero strength (weak / moderate / strong);
**material** = moderate or strong. † marks Magentic fails that reached the correct
answer but were not scored (grading / harness artifacts), so its *substantive* pass
rate is ≈ 5/13, not 1/13.

---

## Summary (per MAS)

| MAS | Topology | Tasks | Pass | Fail | Misalignment **yes** | material (mod+strong) | none | weak | mod | strong |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **Magentic-One** | hub-and-spoke | 13 | 1 (≈5†) | 12 | **9** | **8** | 4 | 1 | 3 | 5 |
| **ChatDev** | waterfall + shared store | 15 | 13 | 2 | **6** | **1** | 9 | 5 | 1 | 0 |

**Locus.** All 8 of Magentic's material cases are **hub→spoke / hub-internal**
(the orchestrator mis-modeling, mis-trusting, or under-informing its spokes); **zero**
are spoke→hub. ChatDev's single material case is **within-phase** (a Programmer
misrepresenting its own work), not a cross-phase distortion.

---

## Magentic-One — per task (13)

| Task (level) | Outcome | Misalignment? | Intensity |
|---|---|:---:|:---:|
| `0383a3ee` BBC Earth bird species (L1) | pass | no | none |
| `27d5d136` logic biconditional (L1) | fail† (LaTeX≠Unicode) | no | none |
| `5d0080cb` fish-bag volume (L1) | fail† (no answer-envelope) | no | none |
| `3f57289b` 1977 Yankee at-bats (L1) | fail (misread table) | no | none |
| `04a04a9b` Nature-2020 p=0.04 count (L2) | fail | yes | weak |
| `5a0c1adf` Malko first name (L1) | fail† ("Claus" reached) | yes | moderate |
| `08cae58d` Apple $50 chart year (L2) | fail | yes | moderate |
| `00d579ea` "Thinking Machine" scientist (L3) | fail | yes | moderate |
| `023e9d44` bottle-deposit road trip (L2) | fail† ("8" at cap) | yes | **strong** |
| `7673d772` Cornell LII deleted word (L1) | fail | yes | **strong** |
| `3cef3a44` botanical vegetables list (L1) | fail | yes | **strong** |
| `72e110e7` BASE DDC-633 flag country (L1) | fail | yes | **strong** |
| `05407167` replit VSCode command (L2) | fail | yes | **strong** |

Outcome counts: 1 correct · 9 wrong · 3 no-answer. Misalignment: none 4 · weak 1 ·
moderate 3 · strong 5. Source: `magentic_one/judging/relational/FAILURE_ANALYSIS_verdicts.md`.

---

## ChatDev — per task (15)

| Task | Outcome (delivered SW) | Misalignment? | Intensity |
|---|---|:---:|:---:|
| `TheCrossword` | fail (crashes on startup) | yes | moderate |
| `StrandsNYT` | fail (crashes on startup) | yes | weak |
| `Checkers` | pass | yes | weak |
| `Gomoku` (control) | pass | yes | weak |
| `CandyCrush` | pass | yes | weak |
| `Wordle` | pass | yes | weak |
| `ConnectionsNYT` | pass | no | none |
| `DouDizhuPoker` | pass | no | none |
| `MonopolyGo` | pass | no | none |
| `Sudoku` | pass | no | none |
| `TicTacToe` | pass | no | none |
| `TextBasedSpaceInvaders` | pass | no | none |
| `ConnectFour` (control) | pass | no | none |
| `Pong` (control) | pass | no | none |
| `TinyRouge` | pass | no | none |

Delivered software works in 13/15 (up from 3/15 in the original GPT-4o
human-annotated runs). Misalignment: none 9 · weak 5 · moderate 1 · strong 0.
Source: `chatdev/judging/relational/FAILURE_ANALYSIS.md`.

---

## Takeaway

**Magentic fails the task often and is misaligned when it does** (8/13 material, all
hub-side); **ChatDev mostly succeeds and is rarely misaligned** (1/15 material,
within-phase). This is a **topology contrast, not a quality verdict**: ChatDev's
review-gated pipeline diffuses and largely repairs coordination errors, so its
residual failures are *single-agent capability* + *shallow verification* rather than
coordination; Magentic's single coordinator is a concentrated point of relational
failure. The peer-topology baseline (**AutoGen GroupChat**) is the third leg of this
comparison — its post-stall-fix verdicts (13 correct / 9 wrong / 4 no-answer; 0 strong
misalignment) live in `autogen_gc/judging/`, but it has no matching `relational/`
broad-lens pass yet, so it is omitted from the tables above rather than scored on a
different scale.
