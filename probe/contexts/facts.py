"""Planted-fact construction and matching.

Each context gets K=6 facts, one per kind. Fact identifiers (parameter names,
file paths, technique names, numeric values) are sampled from pools of
invented, distinctive tokens so that (a) recall can be scored by string match
and (b) facts are not guessable from priors — B can only know them via the
note, the payload, or the raw transcript.

Match semantics: a fact counts as recalled in a piece of text iff every
pattern in ``all_of`` matches AND (``any_of`` is empty or at least one
matches). Patterns are case-insensitive; a trailing ``*`` marks a stem (no
trailing word boundary).
"""

import re

FACT_KINDS = [
    "failed_approach",
    "load_bearing_param",
    "bottleneck",
    "untried_idea",
    "numeric_result",
    "gotcha",
]

QUESTIONS = {
    "failed_approach": "Which approaches did your colleague already try that failed, and why did they fail?",
    "load_bearing_param": "Which exact parameter or setting values did they find critical to keep as-is?",
    "bottleneck": "What did they identify as the real bottleneck or root cause?",
    "untried_idea": "Which ideas did they consider but not yet try?",
    "numeric_result": "What is the best score so far, and which change produced it?",
    "gotcha": "Are there quirks of the evaluator or tooling to watch out for?",
}

PARAM_NAMES = [
    "spill_margin", "gamma_blend", "warp_stride", "fanout_cap", "decay_knee",
    "prefetch_depth", "smoothing_tau", "clip_horizon", "bucket_skew",
    "drop_phase", "merge_window", "probe_offset", "anneal_floor", "stripe_pitch",
]
PARAM_VALUES = ["0.37", "0.73", "113", "6.5", "41", "0.085", "19", "2.25", "57", "0.61"]

FILE_DIRS = ["packer", "rebalance", "quantizer", "scheduler", "iolayer", "kernels", "router"]
# NB: keep these disjoint from every other pool's match keys ("reflow" once
# collided with the "lazy reflow" technique, "seed_map" with the seed gotcha)
FILE_NAMES = [
    "grid_fold", "collate_pass", "merge_pass", "probe_cache", "io_shim",
    "tracer", "bound_check", "edge_sweep", "lane_split", "pack_grid",
]

TECHNIQUES = [
    ("hexagonal seeding", ["hexagonal"]),
    ("cosine ramp warmup", ["cosine ramp"]),
    ("two-phase annealing", ["two-phase anneal*"]),
    ("greedy corner placement", ["greedy corner"]),
    ("block-diagonal preconditioning", ["block-diagonal"]),
    ("stale-gradient averaging", ["stale-gradient", "stale gradient"]),
    ("speculative batching", ["speculative batch*"]),
    ("delta-encoding the cache", ["delta-encod*", "delta encod*"]),
    ("lazy reflow of the buffer", ["lazy reflow"]),
    ("mirrored initialization", ["mirrored init*"]),
]
FAIL_REASONS = [
    ("it oscillated near the boundary and never converged", ["oscillat*", "never converged"]),
    ("memory blew past the 8GB cap on the eval box", ["8GB", "memory"]),
    ("the evaluator timed out on the two largest instances", ["timed out", "timeout"]),
    ("fp16 underflow corrupted the partial sums", ["underflow", "fp16"]),
    ("it broke run-to-run determinism and the grader rejected the attempt", ["determinis*", "rejected"]),
    ("the gain vanished once the warm cache was enabled", ["warm cache", "gain vanished"]),
]

# (text template, all_of, any_of, value pool) — entries inside all_of may be
# lists of alternatives; {v} is filled with a sampled value.
GOTCHAS = [
    ("the evaluator silently caps runtime at {v} seconds — anything longer gets a truncated score",
     [["runtime"], "{v}"], [], ["91", "76", "117"]),
    ("the grader only parses the LAST line printed to stdout, everything else is ignored",
     [["last line", "final line"]], ["stdout", "printed", "parses"], None),
    ("the harness runs each eval twice and keeps the WORSE of the two scores",
     [["worse", "worst"]], ["twice", "two runs", "rerun*"], None),
    ("eval seeds are fixed at {v}, so randomized restarts give identical results",
     [["seed*"]], ["fixed", "{v}", "identical"], ["1234", "777", "4242"]),
]

# trailing * on multiword keys too: B routinely pluralizes ("boundary checks"),
# which a trailing \b would spuriously reject
UNTRIED_IDEAS = [
    ("precomputing the neighbor table offline and shipping it as an artifact", ["neighbor table*", "precomput*"]),
    ("fusing the two normalization passes into one sweep", ["fus*", "normalization pass*"]),
    ("swapping the priority queue for a bucket list", ["bucket list*", "priority queue*"]),
    ("vectorizing the boundary check with masked stores", ["vectoriz*", "boundary check*"]),
    ("caching partial scores between attempts via the scratch dir", ["partial score*", "scratch dir*"]),
    ("splitting the solver into a coarse pass and a polish pass", ["coarse pass*", "polish pass*"]),
]

BOTTLENECK_VERDICTS = [
    "profiling shows ~70% of wall time is spent there, not in the solver everyone keeps tuning",
    "it re-parses the same input on every call; everything downstream just waits on it",
    "it holds the global lock during serialization, which starves the workers",
    "it allocates in the inner loop, and the allocator is what's actually slow",
]


def fact_failed_approach(rng):
    tech, tech_keys = rng.choice(TECHNIQUES)
    reason, reason_keys = rng.choice(FAIL_REASONS)
    return {
        "kind": "failed_approach",
        "text": f"Tried {tech} this attempt — abandoning it: {reason}.",
        "summary": f"{tech} was tried and failed because {reason}",
        "match": {"all_of": [tech_keys], "any_of": reason_keys},
        "aux": {"technique": tech, "reason": reason, "tech_alts": tech_keys},
    }


def fact_load_bearing_param(rng):
    name = rng.choice(PARAM_NAMES)
    value = rng.choice(PARAM_VALUES)
    return {
        "kind": "load_bearing_param",
        "text": (f"Confirmed {name}={value} is load-bearing: nudging it in either "
                 f"direction tanked the score, so it must stay at {value}."),
        "summary": f"parameter {name} must stay at {value}",
        "match": {"all_of": [name, value], "any_of": []},
        "aux": {"param": name, "value": value},
    }


def fact_bottleneck(rng):
    path = f"src/{rng.choice(FILE_DIRS)}/{rng.choice(FILE_NAMES)}.py"
    verdict = rng.choice(BOTTLENECK_VERDICTS)
    fname = path.split("/")[-1]
    return {
        "kind": "bottleneck",
        "text": f"The real bottleneck is {path}: {verdict}.",
        "summary": f"the real bottleneck is {path}",
        "match": {"all_of": [fname.replace(".py", "")], "any_of": []},
        "aux": {"path": path, "verdict": verdict},
    }


def fact_untried_idea(rng):
    idea, keys = rng.choice(UNTRIED_IDEAS)
    return {
        "kind": "untried_idea",
        "text": f"Haven't gotten to it yet, but {idea} still looks promising — nobody has tried it.",
        "summary": f"untried idea: {idea}",
        "match": {"all_of": [keys[0]], "any_of": keys[1:]},
        "aux": {"idea": idea},
    }


def fact_numeric_result(rng, best_score, best_change, change_keys):
    return {
        "kind": "numeric_result",
        "text": (f"New best: {best_score} — that came directly from {best_change}, "
                 f"nothing else changed in that attempt."),
        "summary": f"best score so far is {best_score}, achieved by {best_change}",
        # the raw score also appears in eval records, so recall additionally
        # requires the change attribution, which only the planted line carries
        "match": {"all_of": [str(best_score), change_keys], "any_of": []},
        "aux": {"best_score": best_score, "best_change": best_change},
    }


def _fill(key, v):
    if isinstance(key, list):
        return [k.replace("{v}", v) for k in key]
    return key.replace("{v}", v)


def fact_gotcha(rng):
    tmpl, all_of, any_of, values = rng.choice(GOTCHAS)
    v = rng.choice(values) if values else ""
    text = tmpl.replace("{v}", v)
    return {
        "kind": "gotcha",
        "text": f"Important discovery about the harness: {text}.",
        "summary": f"tooling quirk: {text}",
        "match": {"all_of": [_fill(k, v) for k in all_of],
                  "any_of": _fill(any_of, v)},
        "aux": {},
    }


# ---------- matching ----------

def _pattern(key: str) -> re.Pattern:
    stem = key.endswith("*")
    key = key.rstrip("*")
    pat = re.escape(key)
    if key and (key[0].isalnum()):
        pat = r"\b" + pat
    if not stem and key and key[-1].isalnum():
        pat = pat + r"\b"
    return re.compile(pat, re.IGNORECASE)


def _hit(key, text: str) -> bool:
    """key: pattern string, or a list of alternative pattern strings."""
    if isinstance(key, list):
        return any(_pattern(k).search(text) for k in key)
    return bool(_pattern(key).search(text))


def fact_matches(fact: dict, text: str) -> bool:
    m = fact["match"]
    if not all(_hit(k, text) for k in m["all_of"]):
        return False
    if m.get("any_of"):
        return _hit(m["any_of"], text)
    return True
