# benchmarks/ — framework-agnostic task data

One folder per benchmark, each emitting `tasks.jsonl` in a **single uniform schema**
so any MAS harness (`camel/`, `autogen_gc/`) loads any benchmark the same way. These
are the **hard slices** chosen so the tasks actually exercise multiple agents with
internal loops (not trivially one-shot) — see the selection rationale in `../PLAN.md`.

| Benchmark | Dir | n | `answer_type` | `tool_profile` | Hard? / honesty | Source | Gated |
|---|---|---|---|---|---|---|---|
| **GAIA** | `gaia/` | 28 (L1 8 · L2 15 · L3 5) | `freeform` | `web_compute` | multi-step tool chains; **L3 = hard slice** | local `autogen_gc/tasks/` | — |
| **GPQA-Diamond** | `gpqa_diamond/` | 198 | `mcq` | `none` | PhD-level, expert-validated → **honesty showcase** | `Idavidrein/gpqa` | **yes** |
| **MATH level-5** | `math_l5/` | 134 | `math` | `math` | hardest MATH tier; critic recompute has teeth | `HuggingFaceH4/MATH-500` (lvl 5) | no |

## Record schema (one JSON object per line)
```json
{
  "id": "gpqad_007",
  "bench": "gpqa_diamond",
  "question": "<full prompt the agent sees, incl. A-D options for mcq>",
  "expected_answer": "C",
  "answer_type": "freeform | mcq | math",
  "tool_profile": "none | math | web | web_compute",
  "meta": { "subdomain": "...", "level": 5, "...": "source bookkeeping" }
}
```
`answer_type` drives `camel/harness/scoring.py`: `freeform` (numeric-aware exact),
`mcq` (letter match), `math` (strip `\boxed`/`$`, numeric-aware).

## (Re)generating the data
`tasks.jsonl` is **git-ignored** (derived + reproducible; also keeps gated GPQA
content out of git). Regenerate locally — GPQA/MATH need `HUGGINGFACE_TOKEN` in the
repo-root `.env` (the GPQA token needs *public-gated-repo* access + accepting the
dataset's terms once on its HF page):
```
conda run -n autogen_gc python benchmarks/gaia/prep.py
conda run -n autogen_gc python benchmarks/gpqa_diamond/prep.py
conda run -n autogen_gc python benchmarks/math_l5/prep.py
```
GPQA options are shuffled **deterministically** (seeded by Record ID), so regeneration
is stable. The HF token is never written into `tasks.jsonl`.

## Running through the harness
```
# smoke a few; full set with --all
conda run -n autogen_gc python camel/harness/run_task.py --tasks gpqa_diamond --limit 2
conda run -n autogen_gc python camel/harness/run_task.py --tasks math_l5 --all
conda run -n autogen_gc python camel/harness/run_task.py --tasks gaia gaia_50f58759   # by id
```
`--tasks` resolves a bare benchmark name to `benchmarks/<name>/tasks.jsonl`.
