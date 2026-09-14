# lip — lost-in-propagation relay (fresh build, 2026-09-14)

Instrument: a relay of N identical agents (Qwen3.6-35B-A3B on Tinker), K tool calls each, over an
offline Wikipedia snapshot (FRAMES gold pages pinned to 2024-08-01 + one-hop neighbors, BM25).
Only the free-form handoff text crosses between agents. Any agent may `finish`; agent N must.

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
python lip/harness/run_task.py --arm relay   --n 4 --k 5  --runs 3 --all --workers 8 --skip-done --budget 60
python lip/harness/run_task.py --arm ceiling --n 1 --k 20 --runs 3 --all --workers 8 --skip-done --budget 60
python lip/oracle/run_injection.py --all --m 3 --workers 6 --skip-done --budget 80
python lip/metrics/summarize.py ; python lip/metrics/summarize.py --inj
```
Spend: `python -c "import sys; sys.path.insert(0,'lip/harness'); from llm import spend; print(spend())"`.
