# Cluster infra — SyncHandoff on piranha + tigerfish

Snapshot of the scripts running the GPU-backed stack (2026-07-20). Layout:

```
piranha:/tmp/aij2115/            tigerfish:/tmp/aij2115/
  udocker/      (UDOCKER_DIR)      vllmenv/      (python 3.12 + vllm 0.25.1+cu129)
  synchandoff/  (rsync of repo)    models/qwen36-awq  (QuantTrio AWQ, 24G)
  pyenv/        (pandas/requests/  cache/, fakehome/, tmp/  (ALL caches — home
                 autopep8/fastapi/               is over its NFS quota)
                 uvicorn)          serve.sh  watch_ready.sh
  px/shared/server.py  (proxy)
  run_proxy.sh  run_wave.sh  g1_smoke.sh
  tunnel_key    (ssh -L 8801 piranha->tigerfish; port 8801 is firewalled
                 between machines, ssh is not)
```

Chain: harness (`SYNCHANDOFF_ENV=udocker`, `SYNCHANDOFF_LLM_BASE=http://localhost:8744/m/v1`)
→ proxy on piranha :8744 (think-strip, XML→structured tool calls, `TINKER_BASE=http://localhost:8801/v1`)
→ ssh tunnel :8801 → vLLM on tigerfish GPUs 2,3 (TP2, AWQ,
`--served-model-name Qwen/Qwen3.6-35B-A3B --enable-auto-tool-choice --tool-call-parser hermes --host 0.0.0.0`).

`proxy_server.py` = multi-benchmark-eval `shared/proxy/server.py` PLUS one patch:
`TINKER_ARGS_STYLE=string` makes `_tinkerize_messages` keep
`tool_calls[].function.arguments` as the OpenAI-spec JSON **string** (vLLM
validates this; Tinker demands a **dict** — the default when the env var is
unset). Set in `run_proxy.sh`.

Hard-won environment facts (all committed as code in `harness/env.py` /
`smoke/build_images.sh`):
- no docker rights on either box → udocker (PRoot); images fixed at container
  create-time from `fixpacks/` (git transplant, zeroed-.so restore, mtls cert)
- PRoot needs `-v /dev/shm:/dev/shm` (POSIX semaphores) and an empty bind over
  `/sys/fs/cgroup` (host cgroup v1 `cpu.shares` makes pylint compute 1 CPU)
- home NFS quota ~40G is FULL of the user's own data: every cache must live in
  /tmp (`HOME` is faked for vLLM); `~/.cache/pip` alone had grown to 9G
- torch/vllm wheels must match driver CUDA 12.9: torch 2.11.0+cu128 +
  vllm-0.25.1+cu129 release wheel (PyPI default pulls cu130 → driver too old)
- pkill patterns must not self-match the ssh command line (bracket trick), and
  vLLM workers rename to `VLLM::Worker_TP*` — kill by nvidia-smi PID
- GPUs are shared with other users — NEVER kill non-aij2115 processes; pick
  whichever pair of A100s is free at launch (CUDA_VISIBLE_DEVICES in serve.sh)

Cost: all GPU-stack runs are $0 API; tokens logged to `llm_calls_gpu.jsonl`
(separate from the Tinker-priced `llm_calls.jsonl` that `cost.py` meters).
