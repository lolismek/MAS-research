"""Cell runner: (benchmark x topology x arm) -> scored, metered, persisted traces.

A run = one task through one topology under one arm. Each run gets a unique proxy tag,
so its every model call groups under that tag in shared/proxy/calls.jsonl and we
self-meter tokens from there (Tinker exposes no usage API). Backend is the shared Tinker
proxy route (/m/<tag>/v1), model 'gpt-4o' aliased upstream to Qwen/Qwen3.6-35B-A3B; the
proxy must be running (PROXY_URL).

Traces land in duet/traces/<topology>/<arm>/<bench>/<id>/run_N/. Topologies: relay,
hub, dialogue. Arms: vanilla, full, sop, down, board, extract, board_inert.

Usage (from repo root). --tasks accepts a benchmark name (benchmarks/<name>/tasks.jsonl),
a path, or a duet-local file (duet/tasks/<name>):
  conda run -n autogen_gc python duet/harness/run_task.py --tasks smoke_relay.jsonl --all
  conda run -n autogen_gc python duet/harness/run_task.py --topology hub --tasks smoke_hub.jsonl --all
  conda run -n autogen_gc python duet/harness/run_task.py --tasks pddl pddl_000 --budget 8 --k 3 --arm board

Knobs: --k = shifts (relay) / turn cap T (dialogue); --budget = tool calls per shift
(relay) / per worker (hub) / per turn (dialogue).
"""
import json, os, re, sys, time

from openai import OpenAI

from relay import run_relay, DEFAULT_K, DEFAULT_BUDGET
from hub import run_hub, DEFAULT_WORKER_BUDGET
from dialogue import run_dialogue, DEFAULT_T, DEFAULT_TURN_BUDGET
from agent import Budget
from tools import TOOL_PROFILES
from arms import get_addon
from scoring import classify_outcome, classify_pddl_outcome
import prompts

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # duet/
REPO_ROOT = os.path.dirname(ROOT)                  # multi-benchmark-eval/
TASKS_DIR = os.path.join(ROOT, "tasks")            # duet-local smoke files
BENCH_DIR = os.path.join(REPO_ROOT, "benchmarks")  # framework-agnostic benchmark data
TRACES = os.path.join(ROOT, "traces")
CALLS_LOG = os.path.join(REPO_ROOT, "shared", "proxy", "calls.jsonl")

PROXY = os.environ.get("PROXY_URL", "http://127.0.0.1:8744/v1")
MODEL = os.environ.get("DUET_MODEL", "gpt-4o")     # aliased to Qwen by the proxy

# Tinker console rates for Qwen/Qwen3.6-35B-A3B, USD per MILLION tokens. No usage API ->
# self-meter tokens from calls.jsonl and price them here.
PREFILL_PER_MTOK = float(os.environ.get("DUET_PREFILL_RATE", 0.36))
SAMPLE_PER_MTOK = float(os.environ.get("DUET_SAMPLE_RATE", 0.89))

# Per-task USD safety cap: a runaway task stops and publishes an honest UNKNOWN. A relay
# is K shifts deep, so size it above the most expensive legitimate run (raised over camel's
# single-pipeline $1 because K=3 shifts each with a tool budget cost more).
BUDGET_USD = float(os.environ.get("DUET_BUDGET_USD", "2.0"))

# PDDL bills only env steps toward the shift budget (observe/actions are free lookups).
_BUDGET_TOOLS = {"pddl": {"pddl_step"}}

# Per-topology defaults for the two shared knobs (--k / --budget). relay: K shifts x B
# tool calls; hub: (k unused) x B per worker; dialogue: T turns x B per turn.
_DEFAULTS = {"relay": (DEFAULT_K, DEFAULT_BUDGET),
             "hub": (None, DEFAULT_WORKER_BUDGET),
             "dialogue": (DEFAULT_T, DEFAULT_TURN_BUDGET)}

# What a marker on an edge looks like, per topology (the note-yield axis).
_EDGE_MARKERS = {"relay": prompts.TRUNCATED_MARKER, "hub": prompts.REPORT_MARKER,
                 "dialogue": prompts.MESSAGE_MARKER}


def parse_final(text):
    m = re.findall(r"FINAL ANSWER:\s*(.+)", text or "")
    return m[-1].strip() if m else (text or "").strip()


def client_for(tag):
    base, v1 = PROXY.rsplit("/", 1)
    return OpenAI(base_url=f"{base}/m/{tag}/{v1}", api_key="dummy")


def meter(tag, t0):
    """Sum tokens/calls for this run's tag from the proxy log (lines at/after t0)."""
    pt = ct = n = errs = 0
    if os.path.exists(CALLS_LOG):
        for line in open(CALLS_LOG):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("tag") != tag or r.get("ts", 0) < t0 - 1:
                continue
            n += 1
            if r.get("error"):
                errs += 1
                continue
            pt += r.get("prompt_tokens", 0) or 0
            ct += r.get("completion_tokens", 0) or 0
    cost = round(pt / 1e6 * PREFILL_PER_MTOK + ct / 1e6 * SAMPLE_PER_MTOK, 6)
    return dict(proxy_calls=n, proxy_errors=errs, prompt_tokens=pt,
                completion_tokens=ct, total_tokens=pt + ct, cost_usd=cost)


def _run_topology(topology, question, tool_names, client, addon, *, k, tool_budget,
                  budget_tool_names, usd_budget, env, task):
    if topology == "relay":
        # challenge probes may pre-author the note shift 1 inherits (PLAN challenge suite)
        initial_note = (task.get("meta") or {}).get("challenge_note")
        return run_relay(question, tool_names, client, MODEL, addon, k=k,
                         tool_budget=tool_budget, budget_tool_names=budget_tool_names,
                         usd_budget=usd_budget, env=env, initial_note=initial_note)
    if topology == "hub":
        return run_hub(question, tool_names, client, MODEL, addon,
                       worker_budget=tool_budget, budget_tool_names=budget_tool_names,
                       usd_budget=usd_budget, env=env)
    if topology == "dialogue":
        return run_dialogue(question, tool_names, client, MODEL, addon, t_max=k,
                            turn_budget=tool_budget, budget_tool_names=budget_tool_names,
                            usd_budget=usd_budget, env=env)
    sys.exit(f"unknown topology {topology!r}")


def _edge_payloads(topology, res):
    """What crossed the topology's edges, uniformly (the note-yield axis)."""
    if topology == "relay":
        return res.notes
    if topology == "hub":
        return res.reports
    return res.messages


def run_one(task, topology="relay", arm="vanilla", k=None, tool_budget=None,
            budget_usd=None):
    dk, db = _DEFAULTS[topology]
    k = k if k is not None else dk
    tool_budget = tool_budget if tool_budget is not None else db
    tid = task["id"]
    bench = task.get("bench", "unknown")
    profile = task.get("tool_profile", "none")
    tool_names = TOOL_PROFILES[profile]
    budget_tool_names = _BUDGET_TOOLS.get(profile)
    env = None
    if profile == "pddl":
        from pddl_env import PddlEnv
        env = PddlEnv(task.get("meta") or {})

    runs_dir = os.path.join(TRACES, topology, arm, bench, tid)
    n = 1
    while os.path.exists(os.path.join(runs_dir, f"run_{n}")):
        n += 1
    rundir = os.path.join(runs_dir, f"run_{n}")
    os.makedirs(rundir)
    tag = f"duet_{topology}_{arm}_{tid}_run{n}"

    question = task["question"]
    floc = (task.get("meta") or {}).get("file_local")     # staged attachment (GAIA doc tasks)
    if floc:
        apath = os.path.join(REPO_ROOT, floc)
        question += prompts.ATTACHMENT_NOTE.format(path=apath)

    with open(os.path.join(rundir, "prompt.txt"), "w") as f:
        f.write(question)
    with open(os.path.join(rundir, "expected_answer.txt"), "w") as f:
        f.write(str(task["expected_answer"]))

    print(f"[{topology}/{arm}/{tid}] profile={profile} B={tool_budget} K={k} starting", flush=True)
    t0 = time.time()
    budget = Budget(BUDGET_USD if budget_usd is None else budget_usd,
                    PREFILL_PER_MTOK, SAMPLE_PER_MTOK)
    client = client_for(tag)
    addon = get_addon(arm)
    addon.bind(client, MODEL, budget)
    addon.begin_task(question)
    res = _run_topology(topology, question, tool_names, client, addon, k=k,
                        tool_budget=tool_budget, budget_tool_names=budget_tool_names,
                        usd_budget=budget, env=env, task=task)
    dur = time.time() - t0

    # Note-yield: what actually crossed each edge. A marker means the producer left no
    # usable payload (think-spiral / empty wrap-up / a stretch that established little), so
    # ZERO information transferred there. Logged as a first-class axis so any vanilla-vs-arm
    # gap in transfer robustness is MEASURED, not a hidden confound.
    payloads = _edge_payloads(topology, res)
    marker = _EDGE_MARKERS[topology]
    edges = len(payloads)
    markers = sum(1 for p in payloads if p == marker)
    note_yield = round((edges - markers) / edges, 3) if edges else None

    final = parse_final(res.final)
    expected = str(task["expected_answer"])
    answer_type = task.get("answer_type", "freeform")
    if answer_type == "pddl":
        outcome = classify_pddl_outcome(final, env, committed=res.committed)
    else:
        outcome = classify_outcome(final, expected, answer_type, committed=res.committed)

    result = dict(
        id=tid, topology=topology, arm=arm, run=n, bench=bench, tool_profile=profile,
        answer_type=answer_type, seconds=round(dur, 1),
        k=k, tool_budget=tool_budget,
        final_answer=final, expected_answer=expected, outcome=outcome,
        committed=res.committed, budget_exceeded=res.budget_exceeded, finish=res.finish,
        edges=edges, edge_markers=markers, note_yield=note_yield,
        env=(env.summary() if env is not None else None),
        exact_match=outcome == "correct",
        n_calls=res.n_calls, n_tool_calls=res.n_tool_calls,
        arm_stats=(addon.stats or None),
        per_agent=[dict(role=a.role, finish=a.finish, steps=a.n_steps,
                        tool_calls=a.n_tool_calls, final=a.final[:400]) for a in res.agents],
        **meter(tag, t0))
    # topology-specific axes
    if topology == "relay":
        result.update(shifts_used=res.shifts_used)
    elif topology == "hub":
        result.update(n_subqs=len(res.plan) - (1 if res.followup else 0),
                      degenerate_plan=res.degenerate_plan,
                      followup_used=bool(res.followup))
    elif topology == "dialogue":
        result.update(turns_used=res.turns_used, proposals=res.proposals,
                      contests=res.contests, ratified=res.ratified)

    with open(os.path.join(rundir, "result.json"), "w") as f:
        json.dump(result, f, indent=1)

    # transcripts: relay/hub agents each own a transcript; dialogue agents PERSIST, so
    # per-turn dumps would duplicate the whole history — save the two final states.
    if topology == "dialogue":
        tdump = [dict(role=r, finish="", transcript=s or [])
                 for r, s in sorted(res.states.items())]
    else:
        tdump = [dict(role=a.role, finish=a.finish, transcript=a.transcript)
                 for a in res.agents]
    with open(os.path.join(rundir, "transcript.json"), "w") as f:
        json.dump(tdump, f, indent=1)

    if payloads:                                   # what crossed each edge
        names = {"relay": "handoff_notes.txt", "hub": "reports.txt",
                 "dialogue": "messages.txt"}
        with open(os.path.join(rundir, names[topology]), "w") as f:
            for j, p in enumerate(payloads, 1):
                f.write(f"===== edge {j} =====\n{p}\n\n")
    if topology == "hub":
        with open(os.path.join(rundir, "plan.txt"), "w") as f:
            for j, q in enumerate(res.plan, 1):
                f.write(f"SUBQ {j}: {q}\n")
            if res.followup:
                f.write(f"FOLLOWUP: {res.followup}\n")
    store = addon.store_json()
    if store is not None:                          # the shared store's final contents
        with open(os.path.join(rundir, "store.json"), "w") as f:
            json.dump(store, f, indent=1)

    env_flag = f" goal={'✓' if env and env.goal_reached() else '✗'}" if env else ""
    print(f"[{topology}/{arm}/{tid}] {dur:.0f}s "
          f"final={final!r} expected={expected!r} outcome={outcome}{env_flag}"
          f"{' [BUDGET]' if res.budget_exceeded else ''} calls={res.n_calls} "
          f"tools={res.n_tool_calls} notes={edges - markers}/{edges} tok={result['total_tokens']} "
          f"cost=${result['cost_usd']:.3f} finishes={[a.finish for a in res.agents]}", flush=True)
    return result


def resolve_tasks(spec):
    cands = [os.path.join(BENCH_DIR, spec, "tasks.jsonl"), spec,
             os.path.join(REPO_ROOT, spec), os.path.join(TASKS_DIR, spec)]
    for p in cands:
        if os.path.isfile(p):
            return p
    sys.exit(f"--tasks {spec!r} not found (looked in benchmarks/, cwd, repo root, duet/tasks/)")


def load_tasks(path):
    if path.endswith(".jsonl"):
        return [json.loads(line) for line in open(path) if line.strip()]
    return json.load(open(path))


def pop_opt(args, flag):
    if flag in args:
        i = args.index(flag)
        return args[i + 1], args[:i] + args[i + 2:]
    return None, args


def main():
    args = sys.argv[1:]
    topology, args = pop_opt(args, "--topology"); topology = topology or "relay"
    arm, args = pop_opt(args, "--arm"); arm = arm or "vanilla"
    spec, args = pop_opt(args, "--tasks"); spec = spec or "smoke_relay.jsonl"
    k, args = pop_opt(args, "--k"); k = int(k) if k else None
    budget, args = pop_opt(args, "--budget"); budget = int(budget) if budget else None
    limit, args = pop_opt(args, "--limit")

    if topology not in _DEFAULTS:
        sys.exit(f"unknown topology {topology!r}; have {sorted(_DEFAULTS)}")
    tasks = load_tasks(resolve_tasks(spec))
    sel = tasks if (args == ["--all"] or not args) else [t for t in tasks if t["id"] in args]
    if limit:
        sel = sel[:int(limit)]
    if not sel:
        sys.exit(f"no tasks matched {args}; have e.g. {[t['id'] for t in tasks[:8]]}")
    results = [run_one(t, topology=topology, arm=arm, k=k, tool_budget=budget) for t in sel]
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
