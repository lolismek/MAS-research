# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Research on **memory for multi-agent systems (MAS)**. The active experiment tests whether
inter-agent-misalignment failures from the MAST taxonomy ("Why Do Multi-Agent Systems Fail?",
arXiv 2503.13657) are *structural* (persist with a stronger model) or *capability* (vanish): it
re-runs GAIA tasks the original **Magentic-One failed**, on **MAF-Magentic + gpt-5.4-mini**, then
re-judges old & new traces with one MAST LLM-judge and measures per-mode **survival**.

All model access is through the **Perplexity API** (see gotchas below). The whole `eval/` pipeline
is plain Python 3 (conda base / miniforge), no framework beyond the deps.

## Setup & commands

```bash
# key lives in ./.env (or .env.local), gitignored; config.py auto-loads it — do NOT export manually
pip install agent-framework openai 'markitdown[pdf,docx,xlsx,pptx,xls]' requests

python eval/check_api.py                  # confirm models reachable
python eval/run_mas.py --smoke --level 2  # ONE task end-to-end (cheap sanity check)
python eval/judge.py --file results/runs/<uuid>/0/transcript.txt   # judge one transcript
python eval/run_all.py                    # FULL experiment w/ live per-task progress (the driver)
python eval/analyze.py                    # (re)write results/summary.{json,md}
python eval/grade.py                      # self-test the GAIA scorer (no API)
```

`run_all.py` is the main entry point — it pipelines run→judge per task and prints original-vs-new
labels live. Everything is **resume-safe** (skips any cached run/judge output), so a killed run is
restarted by just re-running; long runs should go in the background with output teed to
`results/run_all.log`. There is no test suite or linter beyond `grade.py`'s self-test and
`python -m py_compile eval/*.py`.

## Pipeline architecture (`eval/`)

Staged, file-based; each stage reads the previous stage's files under `results/`:

1. **`select_tasks.py`** (no API) → `results/tasks.jsonl`. Joins MAD Cat-2 labels
   (`cat2_extraction/cat2_failures.jsonl`) to local GAIA tasks by **prompt-text-in-trajectory
   substring match**, keeps only **original-FAILED** tasks, drops **modality-blocked** tasks
   (audio/video we can't access — see `modality_blocked()`), and stratifies to `N_TASKS` by level
   + failure mode (forces all 2.4/2.5, 2.6 control).
2. **`run_mas.py`** → `results/runs/<uuid>/<run>/{transcript.txt,final_answer.txt,meta.json,events.jsonl}`.
   The MAF-Magentic arm.
3. **`judge.py`** → `results/judged/<uuid>/{original.json,run_<r>.json}`. Ports the MAST judge
   prompt **verbatim** (`prompts.py`, using `MAST/taxonomy_definitions_examples/*`); judges BOTH the
   original console logs and the new transcripts with the SAME `JUDGE_MODEL` so they're comparable.
4. **`analyze.py`** → `results/summary.{json,md}`. Per-mode **survival** = among tasks the re-judged
   *original* flagged for a mode, how often the new system is flagged.

`config.py` is the single source of truth for models, prices, paths, and scale knobs
(`N_TASKS`, `RUNS_PER_TASK`, `LEVEL_MIX`, MAF `MAX_ROUND/STALL/RESET_COUNT`). `llm_client.py` wraps
the Perplexity client. `grade.py` is the GAIA exact-match scorer + `FINAL ANSWER:` extractor.

## Non-obvious gotchas (all hard-won; violating these breaks runs)

- **Perplexity serves frontier models ONLY via the Responses API** at base `…/v1` (so `/v1/responses`).
  `chat.completions` serves **Sonar only**. MAF's `OpenAIChatClient` already uses the Responses API,
  so it works — but `base_url` MUST include `/v1`. `gpt-5.4`/`gpt-5.4-mini` exist; `o4-mini`/o-series
  and `gpt-4o` do **not**.
- **Perplexity's Responses API is stateless** — it rejects `previous_response_id`. Every MAF agent
  must set `default_options={"store": False}` (in `run_mas.py` as `_NO_STORE`) or the 2nd turn 400s.
- **No vision/audio** — Perplexity rejects image input on all models, and markitdown can't transcribe
  audio. Tasks needing to *see* a figure or *hear* audio are excluded by `select_tasks.modality_blocked`;
  text in PDFs/HTML (incl. figure captions/axis labels) is recovered via `read_document`.
- **A MAF workflow instance is single-use** — calling `.run()` twice on it errors
  ("workflow has already been completed"). `run_mas.do_run()` builds a **fresh** workflow per run.
- **`web_search` must return Sonar's `search_results` URLs**, not just the prose summary — agents need
  real links to `fetch_webpage`/`read_document`. (Returning only prose made tasks fail with max-resets.)
- **Judge-parser `(yes|no)` MUST be `\b`-bounded** (`prompts._find_mode`) — the mode NAMES 2.5
  "Ig**no**red Other Agent's Input" and 3.3 "**No** or Incorrect Verification" contain those
  substrings, so an unbounded regex silently forces 2.5/3.3 to "no". This bug originally faked a
  "judge never emits 2.5" result; fixed. Only **2.4 Information Withholding** is genuinely never
  emitted by the 14-mode judge. See `memory/experiment1-results.md`.
- **GAIA grading is strict exact-match** — near-misses (e.g. "Egalitarianism" vs gold "egalitarian")
  score as failures, so "original failed" is sometimes a grading artifact; the judge labels *process*.

## The agents (mirror Magentic-One, per the MAST traces)

`run_mas.build_workflow()`: `StandardMagenticManager` (plan + progress-ledger loop) over three
specialists — **WebSurfer** (`web_search` Sonar + `fetch_webpage`), **ComputerTerminal**
(`run_python`), **FileSurfer** (`read_document` = markitdown for PDF/Office/URL/local path).
`task_prompt()` injects a task's local GAIA attachment path when one exists.

## Data & reference sources (read-only; not code)

- `MAST/` — vendored MAST repo (git state stripped). `traces/MagenticOne_GAIA/gaia_validation_level_{1,2,3}__MagenticOne/<uuid>/0/`
  has each task's `prompt.txt`, `expected_answer.txt`, `console_log.txt`, and any attachment
  (`<uuid>.<ext>`). `taxonomy_definitions_examples/{definitions,examples}.txt` is the judge rubric.
- `cat2_extraction/` — extracted Cat-2 failure records from the MAD dataset (`mcemri/MAD`), the
  source for task selection.
- `references/` — the MAST paper (`2503.13657v3.pdf`), the latent-communication paper, `mast.txt`.

## Project memory

Durable project context (thesis, data findings, framework status, experiment-1 results) lives in
`~/.claude/projects/-Users-alexjerpelea-MAS-memory-research/memory/` (indexed by `MEMORY.md`).
Check it before re-deriving prior decisions.
