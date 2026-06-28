"""Hard cost safety-net for a running batch. Polls the live calls.jsonl tally every
POLL seconds; if total spend since --since reaches --kill-at, sends SIGINT to the
run_batch.py process (graceful + RESUMABLE — finished tasks are saved, rerun the same
command to continue). Defense-in-depth on top of the per-task $1 Budget cap: that cap
bounds any single task, this bounds the whole sweep.

Exits cleanly when run_batch.py is gone (batch finished). Appends every poll to
cost_timeline.log so there's an auditable spend trace.

  python camel/harness/watchdog.py --since <epoch> --kill-at 19 --timeline <path>
"""
import os, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cost_watch import snapshot   # reuse the exact same pricing/tally

POLL = 30


def batch_pids():
    try:
        out = subprocess.check_output(["pgrep", "-f", "run_batch.py"], text=True)
        return [int(x) for x in out.split()]
    except subprocess.CalledProcessError:
        return []


def main():
    a = sys.argv[1:]
    def opt(f, d=None): return a[a.index(f) + 1] if f in a else d
    since = float(opt("--since", "0"))
    kill_at = float(opt("--kill-at", "19"))
    timeline = opt("--timeline", os.path.join(HERE, "cost_timeline.log"))

    tl = open(timeline, "a")
    tl.write(f"# watchdog start since={int(since)} kill_at=${kill_at}\n"); tl.flush()
    while True:
        s = snapshot(since)
        el = (time.time() - since) / 60
        line = (f"{int(time.time())} +{el:5.1f}min  ${s['total']:7.3f}  "
                f"ok={s['ok']} err={s['err']} "
                f"bench={{ {', '.join(f'{b}:${v[0]:.2f}/{v[1]}t' for b, v in sorted(s['by_bench'].items()))} }}")
        tl.write(line + "\n"); tl.flush()

        if s["total"] >= kill_at:
            pids = batch_pids()
            tl.write(f"!! KILL: ${s['total']:.2f} >= ${kill_at} -> SIGINT {pids}\n"); tl.flush()
            for p in pids:
                try: os.kill(p, signal.SIGINT)
                except ProcessLookupError: pass
            break

        if not batch_pids():
            tl.write(f"# batch finished; final tally ${s['total']:.3f} "
                     f"ok={s['ok']} err={s['err']}\n"); tl.flush()
            break
        time.sleep(POLL)
    tl.close()


if __name__ == "__main__":
    main()
