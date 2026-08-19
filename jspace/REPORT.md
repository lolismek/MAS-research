# E2-mini: J-space hand-off readout on a 2-shift relay (jspace/)

**Question.** In a 2-agent relay (shift A hands off to shift B via a capped
free-prose note), does additionally giving B a *J-space readout* of A's silent
workspace — a Jacobian-lens decoding of which vocabulary tokens A's model was
internally considering while it worked, with never-verbalized tokens marked —
improve task outcomes over the plain note channel?

**Status: RUNNING — results pending.**

## Design (fixed by the user; not expanded)

- Benchmark: FanOutQA, first 40 tasks (same `tasks/fanoutqa.jsonl` as
  `chainloss/sweeps/full`, `--limit 40`).
- N=2 only: shift A -> one hand-off edge -> shift B.
- Model (both shifts): `Qwen/Qwen3.5-4B` served by vLLM on tigerfish
  (`--served-model-name gpt-4o`), thinking mode hard-disabled per request via
  `chat_template_kwargs: {enable_thinking: false}` (the model thinks by default;
  the template accepts the kwarg).
- Budget: fixed 16 000 completion tokens per run, split evenly (8 000/shift),
  chainloss mechanics byte-identical across arms.
- Arm `note` (baseline + difficulty check): plain chainloss note arm.
- Arm `note_jspace`: identical, plus B receives a workspace-readout blurb:
  - After A's shift (note written), A's full realized transcript (prompt +
    everything generated, tool schemas included) is re-rendered through the same
    chat template and prefilled through HF Qwen3.5-4B (no generation).
  - Lens readout at **L12** (inside the workspace core L6-L18 of the L3-L30
    range from the j-think CKA analysis): per position,
    `logits = W_U (J_12 h_12)` with `h_12` = output of decoder block 12
    (j-think hook convention), pre-fitted lens `neuronpedia/jacobian-lens`
    rev `qwen-n1000`.
  - top-k = 5 tokens/position; consecutive positions with the same top-1
    collapsed (max-logit representative kept); positions whose whole top-k is
    punctuation/stopwords dropped; individual noise tokens filtered.
  - **SILENT marking (the payload):** a workspace token gets `*` iff its string
    (>=3 chars) never appears, case-insensitively, in A's own generated text
    (assistant turns + the note).
  - Compression to <= ~3000 chars of JSON, prioritising (has-silent, top-1
    logit), re-sorted by position; entry form
    `{"pos": p, "context_token": t, "workspace": ["tokA*", "tokB", ...]}`.
  - B receives note + blurb as separate context layers; the blurb preamble
    explains the instrument and the `*` convention (`prompts.JSPACE_PREAMBLE`).

### Documented confounds (by design, not fixed)
- **Channel width:** the blurb rides OUTSIDE the 2000-char note clip, so the
  `note_jspace` edge is wider than the `note` edge by up to ~3k chars +
  preamble. A win on this arm means "does this KIND of information help", not a
  width-matched channel comparison.
- The extraction re-forward is prefill-only on a 4B — its compute is not billed
  to the relay budget.

## Infrastructure (as actually built)

- tigerfish GPU 3 (40 GB): vLLM 0.27.1+cu129 serving (`--gpu-memory-utilization
  0.55`, `--max-model-len 65536`, hermes tool parser, multimodal inputs
  disabled) + the HF extraction service (`extractor/server.py`, bf16, ~9 GB)
  sharing the card; extraction serialized under a lock.
- Everything on `/tmp/aij2115_scratch` (local NVMe): the home NFS quota is
  hard-exceeded on tigerfish, and NVMe is faster anyway.
  `bootstrap_tigerfish.sh` rebuilds env + model + lens in one command.
- CUDA driver is 12.9: default PyPI torch/vLLM wheels are cu130 and fail
  (`driver too old`); working stack = torch 2.13.0+cu129 (PyTorch cu129 index)
  + vllm 0.27.1+cu129 (wheels.vllm.ai) + `cuda-python==12.9.*`, `numpy<2.4`,
  torchcodec+cu129.
- vLLM's engine died silently during vision-encoder profiling for this
  multimodal model; fixed with `--limit-mm-per-prompt '{"image":0,"video":0}'`.
- Harness: `harness/` = fork of `chainloss/harness` @ HEAD with (a) the
  `note_jspace` arm in `relay.py`, (b) `jclient.py` -> extraction service,
  (c) `extra_body` plumbing for the thinking-off kwarg, (d) direct-vLLM client
  (no Tinker-proxy /m/ route), (e) blurb persistence (`jspace_blurbs.txt`,
  result fields `blurb_chars/entries/silent_frac/error`). Offline tests
  (46 checks; chainloss's own suite minus the unrelated E1 Q&A tests) pass.

## Difficulty check (4B on FanOutQA)

TBD — mean recall of the `note` arm; flag if < 0.05 (floor) or > 0.9 (ceiling).

## Results

TBD: per-arm recall / exact / no_answer; paired per-task delta with sign test +
Wilcoxon; blurb stats; qualitative examples of silent workspace tokens.

## Timeline / incidents

- Home NFS quota exceeded mid-setup (twice) -> moved env, HF cache, and the run
  dir to `/tmp/aij2115_scratch`.
- GPU contention: all 4 GPUs claimed by another user's 4-way vLLM queue for a
  stretch; waited with a monitor, then claimed GPU 3.
- tigerfish went fully unreachable (ping dead, ssh refused) during a vLLM
  relaunch — apparent crash/reboot; recovery via `bootstrap_tigerfish.sh`.
