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

**ChatDev (15)**: the 3 tasks with explicit human cat-2 labels, 9 tasks the human
annotators marked as failed (stateful/interactive games — the regime where ChatDev's
phase-to-phase summary handoff loses information, i.e. where inter-agent
misalignment is mechanistically expected), 3 solved tasks as controls
(Gomoku, Pong, ConnectFour).

**Magentic-One (15)**: 13 failed + 2 succeeded controls; levels 1/2 preferred
(5×L1, 7×L2, 1×L3), 11 without file attachments, 2 with attachments (the files
are present in the local trace dirs). Caveat: GAIA answers are time-anchored
("as of 2023") and the live web has moved — expect some failures to reproduce
for web-drift rather than coordination reasons; the judge pass should separate
these (cat-1/web vs cat-2).

## Reproducing the original numbers

The original runs used GPT-4o. Original traces for all 30 selected tasks are
available: ChatDev trajectories inside MAD, Magentic-One console logs under
`mast_repo/traces/MagenticOne_GAIA/...` (path in each task's `trace_dir`).
These originals can be judge-labelled too, giving a GPT-4o baseline annotation
to compare against our gpt-5.4-mini reproductions.
