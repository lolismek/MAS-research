# Eval framework — MAF-Magentic vs. MAST-GAIA failures

Tests whether **inter-agent misalignment** failures are *structural* (persist on a newer model)
or *capability* (vanish). Re-runs GAIA tasks the original Magentic-One **failed** on
**MAF-Magentic + gpt-5.4-mini**, re-judges old & new traces with one judge, measures per-mode
**survival**. See `../.claude/plans/ok-let-s-use-maf-magentic-snoopy-puffin.md` for the full design.

**STATUS: validated live end-to-end** (1 L2 task: MAS solved it correctly →
graded PASS → judge re-labeled it). The smoke task is one the original
Magentic-One *failed*; with gpt-5.4-mini + the full toolset it now succeeds.

## Setup
```bash
# key: put PERPLEXITY_API_KEY=... in .env (or .env.local) at repo root (gitignored).
# config.py auto-loads it; no need to export.
pip install agent-framework openai 'markitdown[pdf,docx,xlsx,pptx,xls]' requests
```

## Files
- `config.py` — models, prices, paths, N=15, R=3, level mix, MAF limits. Auto-loads `.env`/`.env.local`.
- `grade.py` — GAIA answer scorer + `FINAL ANSWER:` extractor. (self-test: `python eval/grade.py`)
- `select_tasks.py` — builds `results/tasks.jsonl` (no API). **already run**: 15 tasks, L{1:6,2:6,3:3}.
- `prompts.py` — verbatim MAST judge prompt + parser (no API).
- `llm_client.py` — Perplexity client (OpenAI SDK, Responses API + chat fallback).
- `check_api.py` — connectivity/interface smoke test.
- `judge.py` — re-label traces with `JUDGE_MODEL`.
- `run_mas.py` — MAF-Magentic arm. Agents mirror Magentic-One (see Tooling below).
- `analyze.py` — per-mode survival + success delta + cost → `results/summary.md`.

## Run order
```bash
python eval/check_api.py                    # 1. models reachable
python eval/run_mas.py --smoke --level 2    # 2. ONE task end-to-end  ✅ validated
python eval/judge.py --file results/runs/<uuid>/0/transcript.txt   # 3. judge it  ✅ validated
python eval/judge.py --original             # 4. re-judge the 15 original console logs
python eval/run_mas.py                       # 5. full 15x3 MAS runs
python eval/judge.py --runs                 # 6. judge all new transcripts
python eval/analyze.py                       # 7. summary.md
```

## Tooling (mirrors Magentic-One's agents, per the MAST traces)
- `WebSurfer` → `web_search` (Sonar, returns **real source URLs** + snippets) + `fetch_webpage`
  (markitdown HTML→text). `ComputerTerminal` → `run_python`. `FileSurfer` → `read_document`
  (markitdown: PDF/Office/CSV, from path or URL). Manager = `StandardMagenticManager`.

## Verified API facts (the hard-won ones)
- `gpt-5.4-mini` is served **only via the Responses API** at base `…/v1` (`/v1/responses`).
  chat.completions serves **Sonar only**. MAF's `OpenAIChatClient` uses the Responses API, so it
  works — `base_url` MUST include `/v1`. (`OpenAIChatCompletionClient` would NOT work.)
- Perplexity's Responses API is **stateless**: rejects `previous_response_id`. All agents set
  `store=False` so MAF resends full history each turn. (Side effect: input tokens grow per round.)
- **No vision**: Perplexity rejects image input on all models. So Magentic-One's multimodal
  figure-reading is NOT replicated; we rely on PDF/HTML text extraction (recovers most figure
  captions / axis labels / terms that live in text). Documented limitation.
- Real per-call **cost + token usage** captured via a tap on `responses.create` (Perplexity returns
  exact cost). Sonar cost folded in too.

## Measured cost (from the validated runs)
- Successful L2 run: **$0.12**, 17 LLM calls, 31s. A run that loops to max-resets: **~$0.35**, 34 calls.
- Budget for full 15×3=45 MAS runs ≈ **$6–16** + judge (~60 calls × ~$0.02 ≈ $1.2) ≈ **$8–18 total**.

## Decisions / known risks
- MAS = `openai/gpt-5.4-mini`; Judge = `openai/gpt-5.4-mini` (user choice). Same-model self-judging is a
  weak spot → re-judge a subset with `anthropic/claude-sonnet-4-6` (swap `JUDGE_MODEL`) as a check.
- GAIA file-attachment tasks: original binary attachments are NOT in the local traces (only 1/15 seed
  prompts references a file), so those can't be fully reproduced; `read_document` handles URLs/paths.
- Judge temp = 0 (paper used 1.0) for label determinism on a small pilot.
