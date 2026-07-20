# SyncHandoff — runbook

Benchmark for belief/handoff protocols on real out-of-sync repair episodes
(SyncBench substrate). Design + rationale: `PLAN.md`. Everything below assumes
`cd synchandoff/` and the miniforge base python (`python`).

## Prerequisites

- **Proxy**: the shared Tinker proxy from `multi-benchmark-eval` running on
  `localhost:8744` (`shared/proxy/server.py`); it aliases `gpt-4o` →
  Qwen/Qwen3.6-35B-A3B and structures Qwen's tool calls.
- **Docker**: instance images are `xuehang/<instance_prefix>:3.11` from Docker
  Hub (amd64; emulated on Apple Silicon — fine for smoke, use an x86 box for
  batches). Each is ~0.5–2 GB; the 10-repo pilot needs roughly **15–20 GB free**.
- **Data**: `data/syncbench_300_{callee,caller}.csv` from HF
  `xuehang/SyncBench` (gitignored; re-download with `huggingface_hub` if
  missing). `data/repo_dict.json` is committed.

## Pipeline (order of work, plan sec. 12)

```bash
# 0. offline tests (no LLM, no docker)
python -m pytest tests/test_offline.py -q

# 1. G1 smokes (already green 2026-07-20)
python smoke/g1_env_check.py        # env reproduces dataset summaries
python smoke/g1_agent_smoke.py      # Qwen drives the tool loop

# 2. pilot candidates + phase-1 k-sweep  [30-instance batches: USER launches]
python selection.py --n 30
python phase1_runner.py --k 5  --limit 2   # smoke first
python phase1_runner.py --k 5              # then the batch, also --k 8, --k 12

# 3. review gate numbers
python pilot_report.py

# 4. brackets + arms at the chosen k, m  [batches: USER launches]
python build_artifacts.py --k 8            # offline, cheap LLM calls
python phase2_runner.py --k 8 --m 8 --conditions floor,ceiling,oracle
python phase2_runner.py --k 8 --m 8 --conditions vanilla,sop,down,extract
# board arms need the board-family phase 1 first:
python phase1_runner.py --k 8 --family board
python build_artifacts.py --k 8 --arms board,board_inert
python phase2_runner.py --k 8 --m 8 --conditions board,board_inert

# secondary diagnostics (judge-based, never headline)
python probes.py --k 8
python bins.py --k 8
```

Every stage is idempotent (existing outputs are skipped), so batches can be
interrupted and resumed. LLM spend is self-metered to `llm_calls.jsonl`.

## Layout

```
data/            CSVs + repo_dict.json
harness/         instances / splice / env (docker) / llm / agent / prompts / ledger
handoff/arms.py  the arm seam: build_artifact(arm, frozen, instance)
phase1_frozen/   <iid>/<family>_k<k>/{traj.jsonl, repo_state.patch, meta.json, bin.json}
artifacts/       <iid>/<family>_k<k>/<arm>.txt (+ .probe.json)
runs/            <iid>/<cond>_k<k>_m<m>/{traj.jsonl, result.json}
smoke/           G1 checks
```

## Standing constraints

Claude smokes single instances only (~$5-class); the user launches all
30-instance-plus batches. No LLM inference runs locally — model calls go
through the proxy to Tinker.
