"""P4 full-grid sweep: benchmark-ordered phases, parallel workers, sweep-scoped USD cap.

Phases run as barriers (a benchmark finishes completely before the next starts) so each
closes with a full arms x topologies comparison; GAIA is last (user ordering). Inside a
phase, jobs = one (task, topology, arm) each, run as run_task.py subprocesses by a pool
of WORKERS threads (Tinker held 32 in-flight probe calls with flat latency; 24 leaves
proxy-pool headroom for arm machinery calls and other proxy users).

The $100 cap is measured for THIS SWEEP ONLY: cost is summed from shared/proxy/calls.jsonl
over lines with ts >= the sweep's t0 AND tag prefix 'duet_' — every earlier run cached in
the same log is excluded by timestamp. t0 persists in state.json, so a resumed sweep keeps
accumulating instead of resetting the meter. On breach the watchdog SIGTERMs every live
worker process group immediately and writes ABORTED.

Resume: each finished job appends its key to jobs_done.jsonl; relaunching skips them.

Usage (repo root):
  python duet/harness/run_sweep.py --dry          # print the job plan + meter self-test
  python duet/harness/run_sweep.py                # run (resumes if state exists)
"""
import glob
import json
import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                        # duet/
REPO = os.path.dirname(ROOT)
CALLS = os.path.join(REPO, "shared", "proxy", "calls.jsonl")
TRACES = os.path.join(ROOT, "traces")
SWEEP = os.path.join(ROOT, "sweeps", "p4")
PY = sys.executable
# pddlgym lives only in camel_pddl (not autogen_gc) — PDDL jobs must run there.
PY_FOR_SPEC = {"pddl": "/Users/alexjerpelea/miniforge3/envs/camel_pddl/bin/python"}
RUN_TASK = os.path.join(HERE, "run_task.py")

WORKERS = int(os.environ.get("SWEEP_WORKERS", "24"))
CAP_USD = float(os.environ.get("SWEEP_CAP_USD", "100"))
METER_EVERY_S = 20
ATTEMPTS = 2                                        # 1 retry on nonzero exit (proxy blips)

PREFILL_PER_MTOK = 0.36
SAMPLE_PER_MTOK = 0.89

ARMS = ["vanilla", "full", "sop", "down", "board", "extract"]
ARMS_HEADLINE = ARMS + ["board_inert"]              # fever = headline cell (PLAN: inert there only)


def _task_ids(bench, limit=None):
    path = os.path.join(REPO, "benchmarks", bench, "tasks.jsonl")
    ids = [json.loads(l)["id"] for l in open(path) if l.strip()]
    return ids[:limit] if limit else ids


def _challenge_ids(fname):
    path = os.path.join(ROOT, "challenge", fname)
    return [json.loads(l)["id"] for l in open(path) if l.strip()]


def build_phases():
    """[(phase_name, [job...])]; job = (topology, arm, tasks_spec, task_id, budget, env)."""
    fever = _task_ids("fever_compound")
    fanout = _task_ids("fanoutqa")
    pddl = _task_ids("pddl")
    gpqa = _task_ids("gpqa_diamond", limit=50)      # null anchor subset: first 50, stable
    gaia = _task_ids("gaia")
    gaia_env = {"DUET_MAX_TOKENS": "8000"}          # think-rabbit-hole wall-clock lever
    return [
        ("P1-fever", [("relay", a, "fever_compound", t, 1, None)      # B=1: forces real relays
                      for a in ARMS_HEADLINE for t in fever]
                   + [("hub", a, "fever_compound", t, None, None)
                      for a in ARMS_HEADLINE for t in fever]),
        ("P2-fanoutqa", [("hub", a, "fanoutqa", t, None, None)
                         for a in ARMS for t in fanout]),
        ("P3-pddl", [("relay", a, "pddl", t, None, None)
                     for a in ARMS for t in pddl]),
        ("P4-gpqa-null", [("relay", a, "gpqa_diamond", t, None, None)
                          for a in ARMS for t in gpqa]),   # all 6: completeness pass
        ("P5-gaia", [("relay", a, "gaia", t, None, gaia_env)
                     for a in ARMS for t in gaia]),
        # Post-audit addition (user-approved): synthetic probes, all 7 arms.
        # Temporal at B=1 = the fever-relay regime (and successors can't fully
        # re-verify the planted note); spatial keeps the hub worker default.
        ("P6-challenges",
         [("relay", a, "duet/challenge/temporal.jsonl", t, 1, None)
          for a in ARMS_HEADLINE for t in _challenge_ids("temporal.jsonl")]
         + [("hub", a, "duet/challenge/spatial.jsonl", t, None, None)
            for a in ARMS_HEADLINE for t in _challenge_ids("spatial.jsonl")]),
    ]


def job_key(phase, job):
    topology, arm, spec, tid, budget, _ = job
    return f"{phase}:{topology}:{arm}:{spec}:{tid}:B={budget}"


# ---------------------------------------------------------------- sweep-scoped meter
def sweep_cost(t0):
    """USD spent by this sweep: calls.jsonl lines at/after t0 with a duet_ tag."""
    pt = ct = 0
    if os.path.exists(CALLS):
        for line in open(CALLS):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ts", 0) < t0 or not str(r.get("tag", "")).startswith("duet_"):
                continue
            if r.get("error"):
                continue
            pt += r.get("prompt_tokens", 0) or 0
            ct += r.get("completion_tokens", 0) or 0
    return pt / 1e6 * PREFILL_PER_MTOK + ct / 1e6 * SAMPLE_PER_MTOK


class Watchdog(threading.Thread):
    """Re-meters every METER_EVERY_S; on cap breach kills every live worker pgroup."""

    def __init__(self, t0, procs, procs_lock):
        super().__init__(daemon=True)
        self.t0, self.procs, self.lock = t0, procs, procs_lock
        self.abort = threading.Event()
        self.spent = 0.0

    def run(self):
        while not self.abort.is_set():
            self.spent = sweep_cost(self.t0)
            _write_state(self.t0, self.spent, aborted=False)
            if self.spent >= CAP_USD:
                print(f"\n!!! COST CAP: ${self.spent:.2f} >= ${CAP_USD:.2f} — killing all workers",
                      flush=True)
                self.abort.set()
                with self.lock:
                    for p in list(self.procs):
                        try:
                            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                        except Exception:
                            pass
                _write_state(self.t0, self.spent, aborted=True)
                return
            time.sleep(METER_EVERY_S)


def _write_state(t0, spent, aborted):
    with open(os.path.join(SWEEP, "state.json"), "w") as f:
        json.dump(dict(t0=t0, spent_usd=round(spent, 4), cap_usd=CAP_USD,
                       aborted=aborted, updated=time.time()), f, indent=1)
    if aborted:
        open(os.path.join(SWEEP, "ABORTED"), "w").write(f"cap ${CAP_USD} hit: ${spent:.2f}\n")


# ---------------------------------------------------------------- job execution
def newest_outcome(topology, arm, spec, tid):
    d = os.path.join(TRACES, topology, arm, spec, tid)
    if not os.path.isdir(d):
        # spec may be a task-file path (challenge suites) whose bench name differs;
        # the task id is unique, so find its dir under any bench.
        hits = glob.glob(os.path.join(TRACES, topology, arm, "*", tid))
        if hits:
            d = hits[0]
    try:
        runs = sorted((r for r in os.listdir(d) if r.startswith("run_")),
                      key=lambda r: int(r.split("_")[1]))
        res = json.load(open(os.path.join(d, runs[-1], "result.json")))
        return res.get("outcome"), res.get("cost_usd", 0)
    except Exception:
        return "?", 0


def run_job(phase, job, watchdog, procs, procs_lock, logdir):
    topology, arm, spec, tid, budget, env_over = job
    cmd = [PY_FOR_SPEC.get(spec, PY), RUN_TASK,
           "--topology", topology, "--arm", arm, "--tasks", spec, tid]
    if budget is not None:
        cmd += ["--budget", str(budget)]
    env = dict(os.environ, **(env_over or {}))
    logp = os.path.join(logdir, f"{topology}_{arm}_{tid}.log")
    for attempt in range(1, ATTEMPTS + 1):
        if watchdog.abort.is_set():
            return "aborted"
        with open(logp, "a") as lf:
            p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=REPO,
                                 env=env, start_new_session=True)
        with procs_lock:
            procs.add(p)
        rc = p.wait()
        with procs_lock:
            procs.discard(p)
        if rc == 0:
            return "ok"
        if watchdog.abort.is_set():
            return "aborted"
        print(f"  retry {phase} {topology}/{arm}/{tid} (exit {rc}, attempt {attempt})", flush=True)
    return "failed"


def main():
    phases = build_phases()
    total = sum(len(j) for _, j in phases)

    if "--dry" in sys.argv:
        for name, jobs in phases:
            by = {}
            for (topo, arm, spec, tid, b, env) in jobs:
                by.setdefault((topo, arm, b, bool(env)), 0)
                by[(topo, arm, b, bool(env))] += 1
            print(f"{name}: {len(jobs)} jobs")
            for (topo, arm, b, env), n in sorted(by.items()):
                print(f"   {topo:6s} {arm:12s} B={b if b is not None else 'def'}"
                      f"{' env:8K' if env else '':8s} x{n}")
        print(f"TOTAL {total} jobs; workers={WORKERS}; cap=${CAP_USD}")
        # meter self-test: a fake t0 one hour back must see only duet_-tagged recent lines
        probe = sweep_cost(time.time() - 3600)
        print(f"meter self-test (last hour, duet_ tags only): ${probe:.4f}")
        return

    os.makedirs(SWEEP, exist_ok=True)
    logdir = os.path.join(SWEEP, "logs")
    os.makedirs(logdir, exist_ok=True)
    state_p = os.path.join(SWEEP, "state.json")
    done_p = os.path.join(SWEEP, "jobs_done.jsonl")
    fail_p = os.path.join(SWEEP, "jobs_failed.jsonl")

    if os.path.exists(state_p):                      # resume: keep the original t0
        t0 = json.load(open(state_p))["t0"]
        print(f"resuming sweep (t0={t0:.0f}, spent so far ${sweep_cost(t0):.2f})", flush=True)
    else:
        t0 = time.time()
    done = set()
    if os.path.exists(done_p):
        done = {json.loads(l)["key"] for l in open(done_p) if l.strip()}

    procs, procs_lock = set(), threading.Lock()
    watchdog = Watchdog(t0, procs, procs_lock)
    watchdog.start()
    io_lock = threading.Lock()
    counters = dict(done=len(done), failed=0)

    print(f"P4 sweep: {total} jobs total, {len(done)} already done; "
          f"workers={WORKERS}, cap=${CAP_USD}", flush=True)

    for name, jobs in phases:
        todo = [j for j in jobs if job_key(name, j) not in done]
        if not todo:
            print(f"== {name}: all {len(jobs)} jobs already done", flush=True)
            continue
        if watchdog.abort.is_set():
            break
        print(f"== {name}: {len(todo)}/{len(jobs)} jobs to run", flush=True)
        t_phase = time.time()

        def _one(job, phase=name):
            status = run_job(phase, job, watchdog, procs, procs_lock, logdir)
            topo, arm, spec, tid, b, _ = job
            with io_lock:
                if status == "ok":
                    counters["done"] += 1
                    with open(done_p, "a") as f:
                        f.write(json.dumps(dict(key=job_key(phase, job))) + "\n")
                    outcome, cost = newest_outcome(topo, arm, spec, tid)
                    print(f"[{counters['done']}/{total}] {phase} {topo}/{arm}/{tid} "
                          f"outcome={outcome} run=${cost:.3f} sweep=${watchdog.spent:.2f}",
                          flush=True)
                elif status == "failed":
                    counters["failed"] += 1
                    with open(fail_p, "a") as f:
                        f.write(json.dumps(dict(key=job_key(phase, job))) + "\n")
                    print(f"[FAILED] {phase} {topo}/{arm}/{tid} (see logs)", flush=True)

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            list(ex.map(_one, todo))
        if watchdog.abort.is_set():
            break
        print(f"== {name} complete in {(time.time() - t_phase) / 60:.0f} min; "
              f"sweep spend ${sweep_cost(t0):.2f}", flush=True)

    spent = sweep_cost(t0)
    aborted = watchdog.abort.is_set()
    watchdog.abort.set()
    _write_state(t0, spent, aborted=aborted)
    print(f"\nSWEEP {'ABORTED ON CAP' if aborted else 'COMPLETE'}: "
          f"{counters['done']}/{total} done, {counters['failed']} failed, ${spent:.2f} spent",
          flush=True)


if __name__ == "__main__":
    main()
