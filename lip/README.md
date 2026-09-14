# lip — lost-in-propagation relay (fresh build, 2026-09-14)

Instrument: a relay of N identical agents (Qwen3.6-35B-A3B on Tinker), K tool calls each, over an
offline Wikipedia snapshot (FRAMES gold pages pinned to 2024-08-01 + one-hop neighbors, BM25).
Only the free-form handoff text crosses between agents. Any agent may `finish` (free, does not count against K;
after the K-th tool result the agent gets one finish-or-CONTINUE turn); agent N must finish.

External oracle experiment: on a failed run, gpt-5.5 (Perplexity) picks one edge i-1 -> i and writes a
grounded addendum (every sentence cites a prefix span; gpt-5.4-mini verifies support; ungrounded sentences
dropped). The suffix (agents i..N) is resampled under four conditions: enhanced / original / random spans /
full pass-through.

## Layout
- `harness/llm.py` — Tinker chat (XML tool-call parse, reasoning_content) + Perplexity /responses; per-call cost log `traces/calls.jsonl`
- `harness/tools.py` — search / open / finish over the corpus
- `harness/relay.py` — the relay loop, budget, handoff, forced final; `render_prefix` + `spans` (span ids `a{i}.s{n}`, `a{i}.h`)
- `harness/run_task.py` — relay / ceiling arms, scoring, traces under `traces/<arm>/<task>/run_<r>/`
- `harness/judge.py` — normalized exact match + strict gpt-5.4-mini judge
- `harness/closed_book.py` — contamination screen (3 no-tool samples; drop tasks solved >= 2/3)
- `oracle/enhance.py`, `oracle/run_injection.py` — the injection experiment
- `metrics/summarize.py` — per-arm accuracy, found-but-lost, injection paired comparison
- `data/build_corpus.py` — corpus stages `gold` -> `neighbors` -> `index`
- `tests/` — offline tests with fake model/clients (no API): `python lip/tests/test_offline.py`, `python lip/tests/test_oracle_offline.py`

## Run
```
python lip/data/build_corpus.py gold && python lip/data/build_corpus.py neighbors && python lip/data/build_corpus.py index
python lip/harness/closed_book.py                                   # -> data/tasks_screened.jsonl
# batch (decided 2026-09-14): relay N=8 K=2, ceiling N=1 K=16, injection = enhanced vs original only (single oracle-chosen edge)
python lip/harness/run_task.py --arm relay   --n 8 --k 2  --runs 3 --all --workers 8 --skip-done --budget 60
python lip/harness/run_task.py --arm ceiling --n 1 --k 16 --runs 3 --all --workers 8 --skip-done --budget 60
python lip/oracle/run_injection.py --all --arm relay --out inj --conds enhanced,original --m 3 --workers 6 --skip-done --budget 80
python lip/metrics/summarize.py --arms relay,ceiling ; python lip/metrics/summarize.py --inj --inj-dir inj
# --budget = this invocation's spend cap; random / passthrough are smoke-only controls (--conds enhanced,original,random,passthrough)
```
Spend: `python -c "import sys; sys.path.insert(0,'lip/harness'); from llm import spend; print(spend())"`.

## Internal-belief experiment (`lip/internal/`)
Question qualifier stripped (gpt-5.5), kept as a one-sentence private belief about intent (`data/tasks_internal.jsonl`,
140/155 kept; fields `question` = stripped, `original_question`, `belief`, `qualifier`, `qualifier_type`, `alt_reading`).
Arms differ only in who holds the belief in its system prompt (`--holder none|first|all`; `last` available); every agent in
every arm gets the briefing-aware rule line; the briefing never enters the oracle's rendered prefix. Judge sees the original question.
```
python lip/internal/make_tasks.py --workers 8            # generation (done); --sample 20 prints a hand-check sample
for h in none first all; do python lip/harness/run_task.py --holder $h --tasks lip/data/tasks_internal.jsonl \
    --n 8 --k 2 --runs 3 --all --workers 8 --skip-done --budget 40; done
python lip/internal/summarize.py                          # accuracy per arm, interpretation-lost rate, edge-1 externalization
python lip/tests/test_internal_offline.py
```
