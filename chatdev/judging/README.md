# ChatDev judging — MAST 14-mode LLM judge

The formal evaluation for ChatDev: a **two-stage LLM judge** (judge model
**`openai/gpt-5.5`** via the Perplexity Responses API, temperature 0 — a different model
generation than the system under test, to avoid self-judging bias). Per trace:

- **stage_a** — taxonomy-blind close reading (narrative + open-ended findings).
- **stage_b** — the **14 MAST modes**, each with a mandatory verbatim evidence quote.

This differs from how Magentic-One and AutoGen are judged (open-ended / per-trace
verdicts); the methods are preserved per-MAS as their original studies used them.

## ⚠️ The judged outputs here are STALE

`judged/new/chatdev/*.json` were computed on the **now-lost** `gpt-5.4-mini` traces, and
`report/` (LaTeX + PDFs) reflects a prior **combined ChatDev+Magentic** corpus. They are
kept for reference only. **Regenerate the traces (`../traces/`), then re-judge** — outputs
are resume-safe (existing files are skipped), so delete `judged/new/chatdev/` before a
fresh run.

- `judged/original/chatdev/*.json` (4) — calibration verdicts on GPT-4o traces; these
  remain valid (the originals survive in `../traces/original_gpt4o/`).
- `judged/summary.md`, `judged/judge_progress.log` — prior findings + per-trace cost log
  (treat the `new` numbers as stale).
- `report/` — `make_report.py` + generated `gen_*.tex` + `main.pdf`/`short.pdf`. The
  script is a **cross-system** (ChatDev+Magentic) generator from the old combined branch;
  it is a stale reference here and must be adapted before regenerating.

## Run

```bash
# needs PERPLEXITY_API_KEY (repo-root .env) and the external MAST taxonomy:
#   see ../../shared/mast/README.md  (set MAST_REPO or place it at shared/mast/mast_repo/)
conda run -n base python chatdev/judging/judge/judge.py --smoke <a-trace.log>   # one trace
conda run -n base python chatdev/judging/judge/judge.py --original --new --parallel 4
```

Writes `judged/<era>/chatdev/<id>.json`. The judge corpus is scoped to ChatDev here
(`judge.py:corpus()`); Magentic-One is judged separately under `../../magentic_one/`.
