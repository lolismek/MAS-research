# Original-trace screening for inter-agent misalignment (cat-2) symptoms

Every selected failed task's *original* trace (GPT-4o runs) was read by a Claude
subagent and classified: primary failure cause, observed MAST cat-2 symptoms with
verbatim quotes, and a likelihood that inter-agent misalignment contributed.
Screened 2026-06-10. This is the prior justifying the selection — fresh gpt-5.4-mini
runs get their own judge labels.

## ChatDev (12 failed tasks screened)

| Task | Primary cause | Cat-2 symptoms | Likelihood |
|---|---|---|---|
| Sudoku | review-ineffective | 2.2 (ambiguous "check mistakes" never clarified), 2.6 (reviewer claims dead feature works) | **high** |
| TextBasedSpaceInvaders | review-ineffective | 2.6 (fix emitted in chat, never persisted), 2.5 (reviewer re-reports identical defect), 2.3 (win condition dropped) | **high** |
| DouDizhuPoker | review-ineffective | 2.5 (reviewer repeats same comment 3 cycles), 2.4 (rewritten game_logic.py never reached code store), 2.6 | **high** |
| Tiny Rouge | review-ineffective | 2.5 (same comment 3 cycles), 2.4 (cycle-1/2 fixes not persisted), 2.3, 2.6 | **high** |
| TicTacToe | requirement-loss | 2.1 (review loop restarts after "Finished"), 2.6, 2.4 (GUI requirement never reached programmer) | medium |
| Wordle | incomplete-implementation | 2.2 (26-word dict assumption never questioned; reviewer ratified it) | medium |
| ConnectionsNYT | incomplete-implementation | 2.5 (round-1 fix existed only in conversation; reviewer repeats verbatim), 2.6, 2.3 | medium |
| StrandsNYT | incomplete-implementation | 2.4 (cycle-3 fix not persisted), 2.2, 2.6 | medium |
| Checkers | capability | 2.4 (main.py corrupted in handoff), 2.6 — but review loop worked | low |
| TheCrossword | capability | 2.4, 2.6 — fatal defect (contradictory grid) baked in at Coding | low |
| MonopolyGo | incomplete-implementation | 2.2, 2.3 mild — review comments were applied | low |
| CandyCrush | capability | 2.6 (placeholder main.py) — caught and fixed; loop worked | low |

Recurring ChatDev mechanism (4/12 traces): programmer's modification exists in the
chat message but is never parsed into the shared code store, so the reviewer
re-raises the identical comment until the review budget is exhausted — a structural
communication/memory failure (2.4/2.5), directly relevant to the research thesis.

## Magentic-One (13 originally selected + 8 replacement candidates screened)

Kept (cat-2 leaning):

| UUID | L | Primary cause | Cat-2 symptoms | Likelihood |
|---|---|---|---|---|
| 5a0c1adf | 1 | hallucination | 2.5 (final answer discards Assistant's correct analysis), 2.6, 2.3 | **high** |
| 3cef3a44 | 1 | capability | 2.5 (WebSurfer's "green beans are fruit pods" discarded), 2.6 | medium |
| 023e9d44 | 2 | hallucination | 2.2 (invented assumptions), 2.4 (page summary omitted the rates it had open) | medium |
| 05407167 | 2 | premature-termination | 2.1 (re-plan abandoned post at 58% scroll, restarted from search), 2.6 | medium |
| 08cae58d | 2 | capability | 2.5 (orchestrator anchored WebSurfer away from its own correct 2018 row), 2.6 | medium |
| 00d579ea | 3 | web-failure | 2.6 (skipped planned Assistant step, answered directly), 2.3 | medium |
| 366e2f2b | 2 | capability | 2.6 (planned Assistant analysis skipped; answered from garbled PDF extraction) | medium |
| 5d0080cb | 1 | capability | 2.1 (re-plan erased successful PDF access, retried 404 links), 2.6 | medium |
| 72e110e7 | 1 | capability | 2.6 (5 identical orchestrator requests ignored), 2.1 (re-plan lost 25-hit result set) | medium |
| 7673d772 | 1 | verification-gap | 2.6 (WebSurfer answered from prior knowledge, no browsing), 2.2 | medium |

Kept (non-cat-2 failure contrast):

| UUID | L | Primary cause | Note | Likelihood |
|---|---|---|---|---|
| 3f57289b | 1 | capability | WebSurfer misread a fully-visible table; orchestrator rubber-stamped | low |
| 04a04a9b | 2 | capability | whole run failed to operationalize an obtainable lookup; gave up | low |
| 2b3ef98c | 2 | capability | good coordination (recovered from FileSurfer failure), wrong final reasoning | low |

Dropped after screening (no meaningful inter-agent surface or pure single-agent error):
23dd907f (single-agent extraction miss), 42576abe (orchestrator solved single-shot,
zero delegation), 08f3a05f (single-turn off-by-one), 46719c30 (answered from
incomplete evidence; weak cat-2). Also screened and rejected: 7d4a7d1d, 840bfca7,
935e2cff, a0c07678 (all low).

Controls (succeeded originally): 0383a3ee (L1), 27d5d136 (L1).

Magentic-specific recurring mechanism: the orchestrator's ledger re-plan acts as a
lossy memory checkpoint — working URLs, scroll positions, and result sets are
forgotten after "What Went Wrong / New Plan" cycles (2.1-flavored), and planned
Assistant analysis steps get skipped with the orchestrator answering directly (2.6).
