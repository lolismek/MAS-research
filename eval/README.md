# Eval framework — MAF-Magentic vs. MAST-GAIA failures

Tests whether **inter-agent misalignment** failures are *structural* (persist on a newer model)
or *capability* (vanish). Re-runs GAIA tasks the original Magentic-One **failed** on
**MAF-Magentic + gpt-5.4-mini**, re-judges old & new traces with one judge, measures per-mode
**survival**. See `../.claude/plans/ok-let-s-use-maf-magentic-snoopy-puffin.md` for the full design.

## Files
- `config.py` — models, prices, paths, N=15, R=3, level mix, MAF limits.
- `grade.py` — GAIA answer scorer + `FINAL ANSWER:` extractor. (self-test: `python eval/grade.py`)
- `select_tasks.py` — builds `results/tasks.jsonl` (no API). **already run**: 15 tasks, L{1:6,2:6,3:3}.
- `prompts.py` — verbatim MAST judge prompt + parser (no API).
- `llm_client.py` — Perplexity client (OpenAI SDK, Responses API + chat fallback).
- `check_api.py` — connectivity/interface smoke test.
- `judge.py` — re-label traces with `JUDGE_MODEL`.
- `run_mas.py` — MAF-Magentic arm; web tool = Perplexity Sonar.
- `analyze.py` — per-mode survival + success delta + cost → `results/summary.md`.

## Run order (once `PERPLEXITY_API_KEY` is set)
```bash
export PERPLEXITY_API_KEY=...
pip install agent-framework openai        # confirm MAF extra/import names
python eval/check_api.py                   # 1. confirm models reachable + which interface
python eval/run_mas.py --smoke             # 2. ONE task end-to-end (validate MAF<->Perplexity + tools)
python eval/judge.py --file results/runs/<uuid>/0/transcript.txt   # 3. judge that transcript
python eval/judge.py --original            # 4. re-judge the 15 original console logs
python eval/run_mas.py                      # 5. full 15x3 MAS runs
python eval/judge.py --runs                # 6. judge all new transcripts
python eval/analyze.py                      # 7. summary.md
```

## Decisions / known risks
- MAS = `openai/gpt-5.4-mini`; Judge = `openai/gpt-5.4-mini` (user choice). Same-model self-judging is a
  weak spot → re-judge a subset with `anthropic/claude-sonnet-4-6` (swap `JUDGE_MODEL`) as a check.
- **Validate first** (`run_mas.py` header): (1) MAF's chat client must actually reach the frontier id
  via Perplexity (frontier models use the Responses API; if MAF only does chat.completions it may hit
  Sonar). (2) MAF may not expose token usage → MAS cost falls back to a char/4 estimate (approximate).
- GAIA file-attachment tasks: `FileAgent` only reads provided text; tasks needing original binary
  attachments may fail. Consider preferring non-file tasks if this bites.
- Judge temp = 0 (paper used 1.0) for label determinism on a small pilot.
