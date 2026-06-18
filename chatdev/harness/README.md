# ChatDev harness

Runs **native, unmodified ChatDev v1.1.6** against the shared proxy. The only swap is
the model endpoint (`gpt-4o` alias → `gpt-5.4-mini`); ChatDev's own tooling, configs,
and prompts are untouched.

## Prerequisites

1. **Clone ChatDev v1.1.6** (gitignored — not vendored here):
   ```bash
   git clone https://github.com/OpenBMB/ChatDev chatdev/harness/chatdev_repo
   (cd chatdev/harness/chatdev_repo && git checkout v1.1.6)
   ```
   v1.1.6 (2024-11-12) is the last 1.x release — the MAST run window (main is now the
   2.x rewrite). Override the location with `CHATDEV_REPO=/path/to/clone` if needed.
2. **Conda env `chatdev_v1`** (py3.10):
   ```bash
   pip install -r chatdev/harness/chatdev_repo/requirements.txt
   pip install httpx==0.27.2     # openai 1.3.3 breaks on httpx>=0.28
   ```
3. **Proxy up:** `conda run -n base python shared/proxy/server.py` (`:8744`).

## Run

```bash
conda run -n chatdev_v1 python chatdev/harness/run_task.py Gomoku Sudoku
conda run -n chatdev_v1 python chatdev/harness/run_task.py --all [--parallel 3]
```

Each run invokes the repo's `run.py` (`--config Default`, `--model GPT_4O`) with the MAD
`project_name`, then archives the produced WareHouse (code + full dialogue `.log` = the
judge transcript) into `chatdev/traces/<TaskName>/run_N/` with a `result.json`. Runs are
isolated subprocesses on tagged proxy routes (`/t/cd_<name>_runN/`), so `--parallel`
stays attributable. Suggested N: 3.

## Files

- `run_task.py` — the driver (paths re-pointed to this layout: repo → `chatdev_repo/`,
  output → `chatdev/traces/`, tasks → `chatdev/tasks/`).
- `shim/utils.py` — placed first on PYTHONPATH so ChatDev's auto-pip-installed `utils`
  package can't shadow its own `ecl/utils.py`.

## Deviations from the original MAST setup

1. Model: `gpt-4o` → `gpt-5.4-mini` behind the alias (the experiment variable).
2. Code executor runs on the host, not in agbench's Docker container (same executor
   class; `scenario` unchanged). Consider Docker for a full sweep if generated code
   needs isolation.
3. The proxy translates chat.completions ⇄ Perplexity `/v1/responses`, and **drops
   ChatDev's `max_tokens` cap entirely** on the `/t/cd_*` routes. ChatDev sets
   `max_tokens = num_max_token_map["gpt-4o"](=4096) − prompt_tokens` on every call
   (`camel/model_backend.py`); that stale gpt-4o-era budget shrinks as the dialogue
   accumulates the codebase, so late phases (CodeReviewModification, Manual) get only
   a few hundred tokens and the more-verbose gpt-5.4-mini is cut off **mid-line** — a
   systemic truncation source the trace judge misreads as inter-agent failure
   (judging confound "A"). Dropping the cap (model-max default applies) keeps ChatDev
   source unmodified while removing the artifact. The earlier reason for the drop
   still holds for any residual case: a ≤0 budget would otherwise 400 in a fatal
   retry loop, i.e. an infra crash, not a research-relevant failure.
