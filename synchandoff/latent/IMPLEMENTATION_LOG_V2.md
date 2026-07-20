# Latent v2 restart — implementation log (Qwen3-8B dense)

Running log of the PLAN_V2.md execution (2026-07-20, fresh session). The v1
(hybrid-35B) log is IMPLEMENTATION_LOG.md — left intact; v1 cluster state is
archived at piranha:/tmp/aij2115/synchandoff_35b_archive (untouched).

## Directives in effect
- PLAN_V2.md is authoritative: Qwen/Qwen3-8B dense bf16 stock HF; full
  re-run of phase-1/brackets/classic/latent on the new model; k=12/m=8,
  W=300/500 unchanged.
- **User directive (2026-07-20, mid-session), probe training data
  SIMPLIFIED** (overrides PLAN_V2 §L-PROBE v2's matched-pair scenario
  design): generate a large DIVERSE pool of strong-belief vs
  uncertain/unsettled text — no matched-pair construction; diversity does
  the controlling. Must include: domain/style/person diversity; certainty
  NOT always lexically marked (confident text without "clearly/definitely",
  unsettled text without hedge words); convinced-but-wrong labeled as
  strong-belief. Everything else in the probe pipeline unchanged (LR on
  middle-layer residuals, held-out-domain val gate >=0.75, entropy
  correlation reported never trained on, face-validity peak check, peaks ->
  windows -> summarizer; lprobe_randsel + lprobe_shuffled controls).
  Implemented in latent/probe/gen_data.py (10 domains x 5 cells:
  strong_marked / strong_unmarked / strong_wrong / unsettled_marked /
  unsettled_unmarked).

## Code changes (all on lab-test, synchandoff/)
- latent/server.py REWRITTEN for v2 (v1 hybrid-35B version = git history;
  awq_moe.py kept in-tree, no longer imported): stock
  AutoModelForCausalLM.from_pretrained bf16; enable_thinking=False in every
  apply_chat_template (parity with the vLLM no-think template); all 36
  layers carry KV; new arms kv_attn (attention-mass position selection from
  a QTail q_proj tap captured during prefill — q_norm+RoPE applied post-hoc,
  softmax vs cached keys, mean over layers/heads/64 tail queries),
  thought_soft (Soft-Thinking: top-p expected input-embedding, entropy
  cold-stop after min_steps), thought_align (full-softmax expected
  embedding, fixed m); new /probe_score endpoint (linear probe over a
  captured layer's full-position hidden states, NMS peak-pick, decoded
  ±window text; positions override for randsel); prefill_capture gains
  return_entropy.
- handoff/latent_arms.py + handoff/arms.py: v2 arm set =
  lkv_attn (primary) / lkv_last / lkv_rand / lkv_notekv /
  lthought_soft (primary) / lthought_align / lthought_rand (ref=soft) /
  lthought_pool / lprobe / lprobe_randsel / lprobe_shuffled.
  v1 names (lkv, lkv_n75/19, lthought coconut) retired.
- latent/probe/: v2 pipeline = gen_data.py (synthetic pool via vLLM),
  capture_synth.py (raw-text prefill, layers 12/18/24, tail positions
  -1/-4/-7, entropy at last), train.py REWRITTEN (single belief_strength
  probe, GroupKFold by domain, entropy corr reported), annex.py REWRITTEN
  (peaks->windows->one vLLM summary = the artifact; randsel/shuffled
  controls). v1 content-probe files (capture.py turn-ends, labels.py) left
  in place but unused.
- infra/: make_nothink.py (bakes enable_thinking=false into the Qwen3
  template for vLLM), serve_8b.sh (vLLM Qwen3-8B GPU0 :8804, max-model-len
  40960 = Qwen3-8B native max_position_embeddings), run_proxy_8b.sh
  (piranha proxy -> :8804 tunnel; :8747 during smoke, :8744 after
  decommission; TINKER_MAX_TOKENS=8000 — no think trace to absorb budget).
- latent/parity_check.py: endpoints/model via env; smoke_latent.py: v2 arms.

## Infra state
- tigerfish GPU 0: vLLM Qwen/Qwen3-8B :8804 (no-think template, hermes
  parser). GPU 1: HF latent server v2 :8802 (model loads in 7 s).
- piranha: fresh /tmp/aij2115/synchandoff (rsync of repo, v1 outputs
  excluded — phase-1 re-runs on 8B); tunnels :8804 and :8802 up; proxies
  :8747 (text-8B smoke port) and :8745 (latent) up. udocker store +
  fixpacks reused as-is. Old stack (GPUs 2,3 vLLM 35B, :8744 proxy, :8801
  tunnel) up until 8B smoke passed — decommission next.
- Disk (tigerfish /tmp was 98% full): freed ~21 GB of aij2115-owned
  material before the 16 GB model download — stale June pip-unpack tmp
  dirs (~6.3 GB), pip cache, and two RE-DOWNLOADABLE HF caches from another
  project in /tmp/aij2115_scratch/hf (Qwen3-4B 7.6 GB, jacobian-lens
  3.6 GB). The 52 GB Qwen3.6-27B cache there was NOT touched. The 35B AWQ
  model dir (24 GB) will be deleted only after decommission.

## Smoke results (2026-07-20 ~12:00-12:25 ET)
- vLLM 8B direct: "CHAIN_OK" with 3 completion tokens (thinking OFF
  confirmed), structured tool_call emitted. PASS.
- HF-vs-vLLM greedy parity: plain case BYTE-IDENTICAL (85/85 chars);
  tools case content-identical — HF returns the raw `<tool_call>` XML
  (proxy parses it on that path), vLLM parses it server-side; same command
  {"command":"ls tests"}. PASS.
- KV planted-fact (smoke_latent.py, synthetic A transcript, 3 planted
  facts, B prompt mentions none): control 0 hits; lkv_attn 5/5 fact keys
  (non-contiguous selection, 98.45% of tail attention mass captured);
  kv_last(120) 2/5; kv_full and kv_rand 5/5 (transcript short, ~250 tok).
  Fluent everywhere. PASS.
- Soft-token planted-fact: lthought_soft fluent reception but 0 explicit
  fact hits (same for align/pool/rand controls). Cold-stop diagnostic: step
  entropies [0.007, 0.0, 0.014, 0.0, 1.778, 0.693] -> stopped after 5
  vectors (threshold 1.0, min_steps 4) — the summary opening is
  near-deterministic, so rollouts are SHORT. Per the run instructions this
  is LOGGED AS A RESULT, the arm stays, and lthought_pool + controls run so
  the comparison is interpretable. Full log tigerfish:
  /tmp/aij2115/latent/smoke_v2.log.
- Proxy chains from piranha: :8747 chat "PROXY_CHAIN_OK" + structured
  tool_calls; :8745 (latent) chat OK. PASS.

## Phase-1 attempt 1 (12:26 ET) — two harness bugs found and FIXED
First k=12 wave (10 lanes, ~9 min for 28/30) produced G3 = solved 0% /
touched 0% — too clean a zero for capability. Trajectory audit found:
1. **UdockerEnv relative-path bug (harness/env.py `_host_path`)**: read_file
   and write_file resolved relative paths against the rootfs TOP instead of
   /workspace/test_repo. Tally over all 28 trajectories: relative-path
   read_file 181/181 FAILED, absolute-path 34/36 ok. Qwen3-8B habitually
   passes relative paths (the 35B used absolute — the bug was latent in v1).
   Writes with relative paths would also have landed outside the repo (LA
   diff = empty). FIX: resolve relative paths against I.WORKDIR.
2. **Context-window 400s**: one instance died with proxy 400 — prompt
   33.7k tok + TINKER_MAX_TOKENS 8000 > Qwen3-8B's max_position_embeddings
   40960 (v1's 35B served 65536). FIX: TINKER_MAX_TOKENS=2000 (no-think
   replies measure ~60-200 tok; handoff notes <=500), leaving ~39k for
   prompts vs ~34k worst case observed.
phase1_frozen wiped; wave relaunched 12:44 ET with both fixes.

## Next
- Decommission 35B (workers on GPUs 2,3 + :8744 proxy + :8801 tunnel),
  relaunch text proxy on :8744 -> :8804, start second HF worker on a freed
  GPU (:8803) for wave parallelism.
- Phase-1 k=12 plain wave, 10 lanes -> G3 gate (solved 15-60%, touched
  >=50%). Then board-family wave + classic chain ∥ probe chain; latent
  artifacts + A-unsolved-first latent waves; aggregate into results/8b/.
