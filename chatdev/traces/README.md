# ChatDev traces

## State: the `gpt-5.4-mini` run traces were LOST — regenerate them

The original reproduction run dirs were gitignored and never committed, then lost to
worktree mismanagement. This directory is where regenerated traces go; it ships with
only the surviving calibration baseline.

```
traces/
  original_gpt4o/        ← surviving: 15 GPT-4o dialogue logs (calibration anchor), committed
  <TaskName>/run_N/      ← regenerated gpt-5.4-mini runs go here (warehouse/, console.txt, result.json)
```

- **`original_gpt4o/*.log`** — the original GPT-4o ChatDev dialogue logs (one per task).
  These are the judge's calibration anchor (compared against the recovered human
  annotations in `../tasks/`). The judge reads them as the `original` era.
- **Regenerated runs** are produced by `../harness/run_task.py` into
  `traces/<TaskName>/run_N/`, where `<TaskName>` is the MAD `project_name`
  (e.g. `TheCrossword`, `ConnectionsNYT`, `TinyRouge`). The judge reads
  `run_N/warehouse/*.log` as the `new` era.

## To regenerate

See `../README.md` and `../harness/README.md`. In short: clone ChatDev v1.1.6, start the
proxy, then `conda run -n chatdev_v1 python chatdev/harness/run_task.py --all --parallel 3`.
After regenerating, re-run the judge (`../judging/`) — the current judged outputs are
**stale** (computed on the lost traces).
