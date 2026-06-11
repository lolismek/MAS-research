# mini-CORAL

Paper-faithful re-implementation of the CORAL framework (arXiv 2604.01658)
with seams for latent note transport (see `PROBE_PLAN.md` on the probe
branch). Design doc: `MINICORAL_PLAN.md`. Known departures from the paper:
`DEVIATIONS.md`.

## Quick start

```bash
# deps (Mac dev): pyyaml pytest pytest-asyncio numpy scipy openai
# GPU box: bash scripts/setup_gpu.sh

# grade the seed without agents
python -m minicoral validate -c tasks/circle_packing/task.yaml

# model-free test suite
python -m pytest tests/ -q

# real engine smoke (needs model/key; see script header)
python scripts/smoke_engine.py --backend hf --model Qwen/Qwen3-8B

# launch a run
python -m minicoral start -c tasks/circle_packing/task.yaml -o configs/gpu-a100.yaml
python -m minicoral status -c tasks/circle_packing/task.yaml   # leaderboard
```

Per-run output lands in `results/<task>/<ts>/`: shared memory in
`.coral/{public,private,sidecars}/`, agent worktrees in `agents/agent-N/`,
trajectories in `logs/*.traj.jsonl` + `run.events.jsonl`, and
`config.resolved.yaml`.

## Security note

Agents execute arbitrary bash inside their worktrees (per-command timeout,
secret-shaped env vars stripped, file tools path-confined --- but bash itself
is not sandboxed). Run pilots as an unprivileged user on a disposable box.
See DEVIATIONS.md #19.

## Attribution

The circle-packing task (n=26 in the unit square, maximize sum of radii, best
known 2.6359) follows the benchmark used in the CORAL paper's math suite
(after AlphaEvolve / SkyDiscover); seed and grader here are original
implementations.
