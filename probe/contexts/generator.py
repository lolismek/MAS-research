"""Synthetic agent work-session transcripts with planted facts.

Deterministic from (context_id, seed). Transcripts are CORAL-flavored: an
iterative optimize-eval loop with eval records, tool output noise, and
free-form observations. K=6 facts (one per kind) are planted in observation
lines of distinct attempts; everything else is filler drawn from vocabulary
pools disjoint from the fact pools, so string-match recall is unambiguous.
"""

import random

from probe.contexts.facts import (
    fact_bottleneck,
    fact_failed_approach,
    fact_gotcha,
    fact_load_bearing_param,
    fact_numeric_result,
    fact_untried_idea,
    QUESTIONS,
)

DOMAINS = [
    {
        "name": "solver-opt",
        "title": "maximize the packing-density score of the layout solver",
        "cmd": "python run_eval.py --task layout --budget full",
    },
    {
        "name": "pipeline-perf",
        "title": "maximize the throughput score of the ingest pipeline",
        "cmd": "python bench/ingest_bench.py --profile release",
    },
    {
        "name": "train-tune",
        "title": "maximize the validation score of the ranking model",
        "cmd": "python train.py --config sweep.yaml --eval-on-finish",
    },
]

BEST_CHANGES = [
    ("reordering the two merge passes", ["merge pass*", "reorder*"]),
    ("tightening the dedup threshold", ["dedup"]),
    ("pinning the worker pool to physical cores", ["physical core*", "pinn*"]),
    ("switching the outer loop to row-major order", ["row-major", "row major"]),
    ("trimming the padding logic in the writer", ["padding"]),
]

THOUGHTS = [
    "The last change only moved the score by a hair; run-to-run variance is bigger than the delta.",
    "Score curve is flattening — most of the obvious knobs are exhausted.",
    "Let me re-run the profiler before touching anything else.",
    "The diff was small but the eval moved more than expected; need to confirm it's real.",
    "Reverting the previous experiment first so attempts stay comparable.",
    "I'll keep this attempt minimal: one change, one eval.",
    "Reading the harness docs again to make sure I'm not fighting the grader.",
    "Trying a cheap variant first before committing to the full rewrite.",
]

LOGLINES = [
    "loaded {n}k records in {ms} ms",
    "warning: flag --fast-path is deprecated, ignoring",
    "stage[{i}] done in {ms} ms ({n} items)",
    "checkpoint written to .scratch/ckpt_{i:03d}",
    "validator: {n} constraints checked, 0 violations",
    "gc pause {ms} ms during stage[{i}]",
    "worker[{i}] heartbeat ok, queue depth {n}",
    "retry {i} on transient io error, succeeded",
]

PROFILE_FUNCS = ["scan_rows", "emit_blocks", "fold_edges", "hash_join", "flush_segments",
                 "walk_tree", "score_window", "apply_moves"]

OBSERVATIONS = [
    "No regression this time, but nothing gained either.",
    "Small improvement, within noise. Keeping the change since it simplifies the code.",
    "Score dipped slightly; reverted before committing.",
    "Behavior matches the docs. Moving on.",
    "Eval ran clean. The improvement is reproducible across two runs.",
    "That was a dead end, but cheap to check.",
    "Logs look healthy; the earlier warning was unrelated.",
]


def _trajectory(rng, n, best_idx, best_score):
    """Noisy improving score trajectory whose max is exactly best_score at best_idx."""
    start = round(best_score - rng.uniform(0.12, 0.25), 4)
    scores = []
    cur = start
    for i in range(n):
        if i == best_idx:
            cur = best_score
        elif i < best_idx:
            cur = min(best_score - 0.005, cur + rng.uniform(-0.01, 0.035))
        else:
            cur = best_score - rng.uniform(0.002, 0.02)
        scores.append(round(cur, 4))
    return scores


def _tool_output(rng, verbose):
    lines = []
    for _ in range(rng.randint(2, 5) + (4 if verbose else 0)):
        t = rng.choice(LOGLINES)
        lines.append("  " + t.format(n=rng.randint(2, 80), ms=rng.randint(12, 900),
                                      i=rng.randint(0, 9)))
    if verbose:
        lines.append("  cumtime  percall  function")
        for f in rng.sample(PROFILE_FUNCS, 4):
            lines.append(f"   {rng.uniform(0.5, 30):6.3f}   {rng.uniform(0.01, 1):6.3f}  {f}")
    return "\n".join(lines)


def make_context(context_id: str, seed: int) -> dict:
    rng = random.Random(seed)
    domain = rng.choice(DOMAINS)
    target_tokens = rng.randint(2000, 6000)
    # ~180 tokens per attempt block, measured with the Qwen3 tokenizer
    n = max(9, min(32, target_tokens // 180))
    best_idx = rng.randint(max(2, n - 5), n - 2)
    # keep one canonical 4-decimal rendering so transcript, fact text, and
    # match key never disagree (0.742 vs 0.7420 would break \b matching)
    best_score = f"{rng.uniform(0.62, 0.93):.4f}"
    best_change, change_keys = rng.choice(BEST_CHANGES)
    scores = _trajectory(rng, n, best_idx, float(best_score))

    facts = [
        fact_failed_approach(rng),
        fact_load_bearing_param(rng),
        fact_bottleneck(rng),
        fact_untried_idea(rng),
        fact_numeric_result(rng, best_score, best_change, change_keys),
        fact_gotcha(rng),
    ]
    # numeric_result must land on the best attempt; spread the rest elsewhere
    other_slots = rng.sample([i for i in range(1, n) if i != best_idx], 5)
    slot_of = {id(facts[4]): best_idx}
    for f, s in zip([facts[0], facts[1], facts[2], facts[3], facts[5]], other_slots):
        slot_of[id(f)] = s
    fact_at = {slot_of[id(f)]: f for f in facts}

    agent = f"a{rng.randint(1, 9)}"
    out = [
        f"=== SESSION LOG — agent {agent} — objective: {domain['title']} ===",
        f"(iterative optimize-eval loop; evals scored by the shared grader; session {rng.randint(3, 40)})",
        "",
    ]
    best_so_far = 0.0
    for i in range(n):
        commit = "".join(rng.choices("0123456789abcdef", k=7))
        verbose = rng.random() < 0.3
        score = scores[i]
        best_so_far = max(best_so_far, score)
        out.append(f"--- attempt {i + 1} (commit {commit}) ---")
        out.append(f"thought: {rng.choice(THOUGHTS)}")
        out.append(f"$ {domain['cmd']}")
        out.append(_tool_output(rng, verbose))
        out.append(f"[eval] attempt {i + 1}: score={score:.4f} (best so far {best_so_far:.4f})")
        if i in fact_at:
            out.append(f"observation: {fact_at[i]['text']}")
            if rng.random() < 0.5:
                out.append(f"observation: {rng.choice(OBSERVATIONS)}")
        else:
            out.append(f"observation: {rng.choice(OBSERVATIONS)}")
        out.append("")
    out.append(f"=== END OF SESSION LOG (best score {best_score}) ===")
    transcript = "\n".join(out)

    fact_records = []
    for j, f in enumerate(facts):
        fact_records.append({
            "fact_id": f"{context_id}_f{j}",
            "kind": f["kind"],
            "attempt": slot_of[id(f)] + 1,
            "text": f["text"],
            "summary": f["summary"],
            "match": f["match"],
            "question": QUESTIONS[f["kind"]],
        })
    return {
        "context_id": context_id,
        "seed": seed,
        "domain": domain["name"],
        "objective": domain["title"],
        "n_attempts": n,
        "best_score": best_score,
        "approx_tokens": int(len(transcript) / 3.16),
        "transcript": transcript,
        "facts": fact_records,
    }
