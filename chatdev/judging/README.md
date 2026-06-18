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

## Trace-artifact confounds (why the stale numbers over-count misalignment)

Close reading of the stale judgments found that much of the apparent inter-agent
misalignment is **trace/harness artifacts**, not MAS behavior. The current code
neutralizes three of the four; the re-judge will reflect the fixes:

- **A — mid-line completion truncation.** ChatDev's `max_tokens = 4096 − prompt`
  budget truncates the verbose gpt-5.4-mini, and incomplete code reads as
  withholding / ignored-fix / weak-verification. Fixed in the **proxy** (drops the
  cap on `/t/cd_*`); see `../harness/README.md` deviation 3. *Requires regenerating
  traces* to take effect.
- **B — markdown-mangled state dumps.** ChatDev's logger renders its `[SystemMessage]`
  / `| Parameter | Value |` state tables through markdown+HTML, mangling code shown
  there (`__init__`→`init`, `<Button-1>`→``, `<`→`&lt;`) while the dialogue stays
  intact — the judge read this as code/state corruption *between agents*. Fixed by an
  artifact note injected into both judge stages (`prompts.py:RENDERING_ARTIFACTS`),
  identical for both eras so old-vs-new stays comparable. (The note explicitly does
  **not** excuse genuinely empty state like an empty `requirements` — confound "D",
  a real but single-agent extraction issue, is left to be judged normally.)
- **C — the judge's own input truncation.** `[MIDDLE OF TRACE TRUNCATED]` was inserted
  by `judge.py` for traces over the char cap, then misreported as a ChatDev event.
  `MAX_TRACE_CHARS` raised 400K→1M (env-overridable) and the marker is now explicitly
  attributed to the harness, with a matching note in both prompts.

Net effect on the **already-written** `judged/` files: none — they are stale and must
be regenerated. These fixes change what the *next* judge run sees.

## Run

```bash
# needs PERPLEXITY_API_KEY (repo-root .env) and the external MAST taxonomy:
#   see ../../shared/mast/README.md  (set MAST_REPO or place it at shared/mast/mast_repo/)
conda run -n base python chatdev/judging/judge/judge.py --smoke <a-trace.log>   # one trace
conda run -n base python chatdev/judging/judge/judge.py --original --new --parallel 4
```

Writes `judged/<era>/chatdev/<id>.json`. The judge corpus is scoped to ChatDev here
(`judge.py:corpus()`); Magentic-One is judged separately under `../../magentic_one/`.
