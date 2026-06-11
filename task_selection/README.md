# Task selection for ChatDev (1.0) & Magentic-One failure reproduction

Goal: reproduce MAST-style failure cases — biased toward **category 2 (inter-agent
misalignment)** but not exclusively — with both systems running **gpt-5.4-mini via
the Perplexity key**, then study whether memory / communication interventions help.

## Files

- `chatdev_tasks.json` — 15 ProgramDev tasks (full task prompts included).
- `magentic_gaia_tasks.json` — 15 GAIA validation tasks (question, expected answer,
  level, attachments, original-run outcome, pointer to original trace dir).
- `magentic_gaia_all_outcomes.json` — computed success/failure for all 165 local
  Magentic-One GAIA traces (120 failed / 45 succeeded under GPT-4o).
- `mast_human_annotations_recovered.csv` — human master annotation table recovered
  from MAST repo git history (`git show 84a56a8^:annotations.csv`; the file was
  deleted upstream). Old-taxonomy columns; covers ChatDev/MetaGPT/HyperAgent/AppWorld/AG2.
- `build_selection.py` — reproduces everything above. Needs `mast_repo/` (clone of
  https://github.com/multi-agent-systems-failure-taxonomy/MAST, gitignored) and
  HF access to `mcemri/MAD` for ChatDev task prompts.

Larger-MAS extension (MacNet + DyLAN; see reproduction/README.md):

- `macnet_srdd_tasks.json` — 10 SRDD tasks (MacNet's native benchmark), seeded
  sample of 10 distinct categories × 1 task via `sample_srdd.py` (source CSV
  cached under `data/`, gitignored). No ground-truth outcome exists; success is
  the judge's verdict. MacNet's chain/mesh configs need no task file of their
  own — they reuse `chatdev_tasks.json` verbatim (the architecture-only
  comparison).
- `dylan_tasks.json` — 15 MMLU test items: 12 that a single gpt-5.4-mini call
  answered wrong + 3 it answered right (controls), screened from 120 candidates
  across 6 hard subjects by `screen_dylan.py` (baseline failure rate 36/120;
  full pool outcomes in `dylan_screen_results.json`). DyLAN has no original
  MAST traces, so there is no cat-2 prior — difficulty screening replaces
  trace screening, and the same single-model baseline doubles as the
  MAS-vs-single-model comparison point.

## ⚠️ MAD dataset annotations are broken — do not use

The HF dataset `mcemri/MAD` (`MAD_full_dataset.json`, both the 2025-05-16 and
2025-07-21 revisions) contains only **206 unique `mast_annotation` rows for 1,242
traces**: the annotation is purely a function of the integer row index, so traces
from *different systems and benchmarks* that share an index have identical labels
(verified: 193/193 collision groups identical; 0 differ). The trace↔annotation
mapping was lost in packaging. Any per-trace failure-mode statistics computed from
MAD are meaningless. The trajectories themselves are fine and are used here only
as the source of ProgramDev task prompts.

Consequences for label provenance:

- **ChatDev**: human labels recovered from the deleted `annotations.csv` (32 game
  tasks, old column names mapped to final MAST modes: trajectory restart→2.1,
  fail to elicit clarification→2.2, derailing→2.3, withholding info→2.4, ignoring
  suggestions→2.5, thought/response misalignment→2.6). Labels are sparse — only
  TicTacToe (2.1), Wordle (2.2), Sudoku (2.2) carry explicit cat-2 marks; the
  richer per-mode ChatDev labels lived in a private Google Sheet referenced by
  the CSV and are not recoverable. The companion per-trace repo
  (LakshyAAAgrawal/MultiAgentFailureTaxonomyAnnotations) is private/deleted.
- **Magentic-One**: no recoverable per-trace MAST labels at all. Selection is by
  *computed outcome* of the original GPT-4o runs (final `FINAL ANSWER:` line vs
  `expected_answer.txt`, normalized exact match). MAST labels for our reproduced
  runs will come from our own LLM judge.

## Selection rationale

Every candidate failed task's ORIGINAL trace was read and screened for cat-2
symptoms (verdicts + quoted evidence in `trace_screening.md`; embedded in the
task JSONs as `cat2_likelihood_screened`). So the cat-2 prior is observed, not
assumed.

**ChatDev (15)**: 4 high-likelihood cat-2 (Sudoku, TextBasedSpaceInvaders,
DouDizhuPoker, Tiny Rouge), 4 medium (TicTacToe, Wordle, Connections, Strands —
TicTacToe/Wordle/Sudoku also carry explicit human cat-2 labels), 4 low as
non-cat-2 failure contrast, 3 solved controls (Gomoku, Pong, ConnectFour).
Recurring mechanism in the high group: programmer's fix exists in chat but never
persists to the shared code store, so the reviewer repeats the identical comment
until the review budget burns out (2.4/2.5).

**Magentic-One (15)**: 1 high + 9 medium cat-2 failures, 3 low (non-cat-2
contrast), 2 succeeded controls; 8×L1, 6×L2, 1×L3; 2 with text-parseable
attachments (files in local trace dirs; image-attachment tasks excluded since
gpt-5.4-mini has no vision). Recurring mechanism: the orchestrator's ledger
re-plan acts as a lossy memory checkpoint — working URLs and result sets are
forgotten after "What Went Wrong / New Plan" cycles (2.1), and planned Assistant
analysis steps get skipped (2.6). Caveat: GAIA answers are time-anchored and the
web has drifted — the judge pass should separate web-decay failures from
coordination failures.

## Reproducing the original numbers

The original runs used GPT-4o. Original traces for all 30 selected tasks are
available: ChatDev trajectories inside MAD, Magentic-One console logs under
`mast_repo/traces/MagenticOne_GAIA/...` (path in each task's `trace_dir`).
These originals can be judge-labelled too, giving a GPT-4o baseline annotation
to compare against our gpt-5.4-mini reproductions.
