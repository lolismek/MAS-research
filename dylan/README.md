# DyLAN (vanilla) — via the G-Memory harness

This folder is the **DyLAN** (Dynamic LLM-Agent Network) multi-agent system, brought in **vanilla**
(no cross-trial memory). It is a standalone sibling of `../macnet`: both reuse the same harness from
the [G-Memory](https://arxiv.org/abs/2506.07398) repo, which vendors AutoGen / DyLAN / MacNet under a
shared task/env/reasoning stack. This arm dispatches `--mas_type dylan` and runs with
`--mas_memory empty`.

DyLAN itself: a layered grid of `round_num × node_num` LLM "neurons" that answer, read each other's
outputs within a round, check for consensus, rank/deactivate weak agents mid-way, and finish each
environment step with a majority answer or a decision agent's summary. See
`tasks/mas_workflow/dylan/` (`dylan.py`, `neuron.py`, `dylan_prompt.py`).

## What "vanilla" means here
- **Memory = `empty`.** The `MASMemoryBase` retriever returns nothing and the cross-trial hooks are
  no-ops, so DyLAN runs with in-trial state only. The other memory baselines (ChatDev, MetaGPT,
  Voyager, Generative, MemoryBank, G-Memory) are still vendored under `mas/memory/` as artifacts but
  are **not wired up** — there is no Chroma DB / external memory here by design.
- **No embeddings required.** DyLAN's per-neuron edge weights are write-only (never read by
  consensus / ranking / summary), so `neuron.py` builds a single shared `EmbeddingFunc` lazily and
  degrades to a no-op when `sentence-transformers` is absent — matching MacNet, which uses no
  embeddings. Behavior is unchanged; vanilla runs need no local embedding model.
- **Backend = the shared local proxy.** `mas/llm.py` points at `http://127.0.0.1:8744` and calls the
  `/m/<tag>/v1` route (Tinker/Qwen3.6). Every call is attributable via `DYLAN_TAG` (default
  `dylan_dev`) in `../shared/proxy/{calls,raw_calls}.jsonl`.

## Setup
```
conda activate macnet312          # py3.12; openai + pyyaml + tqdm + numpy is all vanilla needs
# (FEVER/PDDL run with no heavy deps; ALFWorld/SciWorld need their own backends installed)
```

## Run
```
# Option 1 — shell script (FEVER, vanilla):
./run_mas.sh

# Option 2 — explicit, e.g. a 1-task smoke:
python tasks/run.py --task fever --reasoning io --mas_memory empty \
    --mas_type dylan --max_trials 15 --limit 1 --model Qwen/Qwen2.5-14B-Instruct
```
Tasks: `fever`, `pddl` (cheap, pure-Python envs), `alfworld`, `sciworld` (need their backends).
Run outputs land in `./.db/<model>/<task>/dylan/<memory>/` (gitignored).

## Attribution
This is the DyLAN baseline as vendored by G-Memory (Zhang et al., 2025); DyLAN is from
*"Dynamic LLM-Agent Network: An LLM-agent Collaboration Framework with Agent Team Optimization"*
(Liu et al., 2023). The harness, datasets, and baseline implementations come from G-Memory /
AgentSquare / ExpeL.

```
@article{zhang2025g-memory,
  title={G-Memory: Tracing Hierarchical Memory for Multi-Agent Systems},
  author={Zhang, Guibin and Fu, Muxin and Wan, Guancheng and Yu, Miao and Wang, Kun and Yan, Shuicheng},
  journal={arXiv preprint arXiv:2506.07398},
  year={2025}
}
```
