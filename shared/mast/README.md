# MAST taxonomy (external dependency)

The ChatDev judge (`chatdev/judging/judge/judge.py`) scores traces against the
**MAST 14-mode** failure taxonomy. The mode *definitions* and *examples* live in
the external MAST repo, which is **gitignored** here (not redistributed).

## What depends on it

- `chatdev/judging/judge/judge.py` reads:
  - `taxonomy_definitions_examples/definitions.txt`
  - `taxonomy_definitions_examples/examples.txt`
- `chatdev/tasks/build_selection.py` (task-selection reproducibility) reads the
  MAST traces / annotations.
- `magentic_one/harness/run_task.py` and `autogen_gc/harness/run_task.py` resolve
  each reused task's original `trace_dir` (e.g. `mast_repo/traces/MagenticOne_GAIA/...`)
  relative to the MAST clone.

## How to provide it

Place a clone of the MAST taxonomy repo at `shared/mast/mast_repo/` so that
`shared/mast/mast_repo/taxonomy_definitions_examples/{definitions,examples}.txt`
exist, **or** point the scripts at an existing clone via env vars:

```bash
export MAST_REPO=/path/to/mast_repo            # used by the judge
export MAST_REPO_ROOT=/path/to/parent_of_mast_repo   # used by the MAS runners for trace_dir
```

Defaults (no env set): the judge looks in `shared/mast/mast_repo/`; the MAS
runners resolve `trace_dir` relative to the repo root.

> Provenance: the human-annotation slice the task selection relied on was
> recovered from the (now deleted) MAST annotations repo — see
> `chatdev/tasks/mast_human_annotations_recovered.csv` and
> `chatdev/tasks/README.md`. Only the ChatDev re-run and re-judge actually need
> this dependency; the committed Magentic-One and AutoGen analysis products do not.
