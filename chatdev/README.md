# ChatDev

**ChatDev v1.1.6** — a software-company MAS (waterfall of role-played phases over a
shared code store) on **15 MAD** game/software tasks. Source: the `chatdev-magentic-eval`
branch. Model: `gpt-5.4-mini` via `shared/proxy`.

> ⚠️ **The raw traces were LOST** (a prior gitignored run dir + worktree mismanagement).
> The full *setup* is preserved here so they can be **regenerated**, after which the
> evaluation is **re-judged**. The existing judged outputs are **stale** (computed on the
> lost traces) — see `judging/README.md`.

## Layout

- **`tasks/`** — `chatdev_tasks.json` (15 tasks: 12 cat-2-screened + 3 solved controls),
  `mast_human_annotations_recovered.csv` (human labels recovered from the deleted MAST
  repo), `trace_screening.md` (per-task cat-2 likelihood), `build_selection.py`
  (reproducibility), `README.md` (selection rationale).
- **`harness/`** — `run_task.py` invokes native ChatDev's own `run.py` per task and
  archives the WareHouse (code + dialogue `.log`). `shim/utils.py` guards `import utils`
  against ChatDev's auto-pip-installs. See `harness/README.md` for the clone + env steps.
- **`traces/`** — `original_gpt4o/` holds the 15 surviving **GPT-4o calibration** traces
  (the judge's anchor). Regenerated `gpt-5.4-mini` runs land in `traces/<TaskName>/run_N/`.
  See `traces/README.md`.
- **`judging/`** — the formal **two-stage gpt-5.5 MAST 14-mode** LLM judge (`judge/`),
  its outputs (`judged/`, **stale**), and the LaTeX report (`report/`, stale).

## Reproduce (the intended workflow here)

```bash
# 1. clone ChatDev v1.1.6 + create env  (see harness/README.md)
# 2. start proxy:  conda run -n base python shared/proxy/server.py
# 3. regenerate traces:
conda run -n chatdev_v1 python chatdev/harness/run_task.py --all --parallel 3
# 4. re-judge (needs the MAST taxonomy — see ../shared/mast/README.md):
conda run -n base python chatdev/judging/judge/judge.py --new --parallel 4
```
