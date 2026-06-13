# Judge results: 30 new gpt-5.4-mini traces + 4 calibration anchors

Judge: openai/gpt-5.5, temp 0, two-stage (taxonomy-blind close reading ->
evidence-required MAST labels). Code: `reproduction/judge/`. Cost: ~$34.
Per-trace JSONs in `judged/{original,new}/{chatdev,magentic}/`; progress log
with per-trace cost in `judge_progress.log` (v1-prompt run archived as
`judge_progress_v1.log`).

## Calibration (4 original-trace anchors vs ground truth)

- Sudoku: exact match with human row (1.1, 2.2 both found).
- DouDizhuPoker: screening-verified 2.4/2.5 both found with correct quotes.
- TicTacToe: human 2.1 missed; Wordle: human 2.2 missed.
- Verdict: **high recall on commission modes (2.4/2.5/2.6, 3.x); ~50% recall
  on omission modes (2.1/2.2)** — treat 2.1/2.2 frequencies as lower bounds.
- Precision is NOT measurable (human labels sparse); every flag carries a
  verbatim quote for case-by-case verification. Spot-checks held up.

## Mode frequencies, new traces (n=15 each)

| mode | ChatDev | Magentic | reading |
|------|---------|----------|---------|
| 2.4 Information Withholding | **15** | 4 | ChatDev's code-store channel loses artifacts in EVERY run, incl. the 3 working-game controls |
| 2.5 Ignored Other Agent's Input | **15** | **13** | pervasive in both |
| 2.6 Action-Reasoning Mismatch | 12 | 13 | |
| 2.1 / 2.2 / 2.3 | 7 / 5 / 6 | 4 / 8 / 8 | lower bounds (see calibration) |
| 3.1 / 3.2 / 3.3 verification | 13 / 13 / 13 | 13 / 13 / 13 | rubber-stamp verification near-universal |

Architecture signature: ChatDev (waterfall + shared code store) is 2.4-heavy —
information exists but never persists to the only inter-phase memory.
Magentic (star topology) is 2.5-heavy but 2.4-light — the orchestrator sees
everything (little withholding) but discards specialist input.

## Stage-A mechanism clusters (free-form `kind` labels, 30 traces)

ChatDev-specific: state corruption (10), truncated output/code/patch (17
combined — root cause: ChatDev's own 4096-token completion budget, verified
by token accounting), lost artifact (5), redundant reflection (8), scope
drift (11), shallow/weak testing (8).
Magentic-specific: unsupported final answer (7), unused tools (5), missed
verification (4).
Excluded as reproduction artifacts: "model mismatch" (7; AutoGen UserWarning
from the proxy's model-name alias — proxy now echoes the dated snapshot name),
"logging failure" (11; ChatDev's visualizer Flask app not running locally),
"timestamp mismatch" (7; log clock format).

## Headline for the thesis

The 2.4 mechanism in ChatDev fired in 15/15 runs under gpt-5.4-mini including
all 3 succeeded controls — it is a property of the architecture's
communication channel, not of task difficulty or model capability. The
channel failure chain (budget-truncated emission -> extractor silently drops
file -> reviewer repeats identical comment -> verification rubber-stamps) is
fully evidence-quoted across traces and suggests a concrete intervention:
persistent artifact store with receipt verification; falsifiable via the
repeated-reviewer-comment signature.

## DyLAN-MATH arm (added 2026-06-11)

15 MATH-500 level-5 traces judged; fingerprint + four evidence-quoted case
studies (the answer/score extraction collision, ranker discarding correct
agents, the one conformity flip, grading artifacts) in
`dylan_math_cases.md`. Per-trace verdicts in `new/dylan-math/`.
