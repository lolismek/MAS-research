"""Re-label traces with the MAST LLM-as-a-judge (Perplexity, JUDGE_MODEL).

Judges BOTH the original Magentic-One console logs and our new MAF transcripts
with the SAME judge so old-vs-new is comparable. Resume-safe (skips existing).

Usage:
  python eval/judge.py --original          # judge each seed task's original console_log.txt
  python eval/judge.py --runs              # judge every results/runs/<uuid>/<r>/transcript.txt
  python eval/judge.py --file PATH [--out OUT]   # judge a single transcript (smoke test)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
from llm_client import call_llm
from prompts import build_judge_prompt, parse_judge_response

MAX_TRACE_CHARS = 500_000          # safety vs context window; logs are usually far smaller

_defs = _examples = None
def _rubric():
    global _defs, _examples
    if _defs is None:
        _defs = C.DEFINITIONS_TXT.read_text(errors="ignore")
        _examples = C.EXAMPLES_TXT.read_text(errors="ignore")
    return _defs, _examples


def judge_trace(trace_text: str) -> dict:
    if len(trace_text) > MAX_TRACE_CHARS:        # keep head + tail (where failures show)
        head = trace_text[: MAX_TRACE_CHARS // 2]
        tail = trace_text[-MAX_TRACE_CHARS // 2:]
        trace_text = head + "\n...[TRUNCATED]...\n" + tail
    defs, examples = _rubric()
    prompt = build_judge_prompt(trace_text, defs, examples)
    raw, usage = call_llm(prompt, C.JUDGE_MODEL, temperature=C.JUDGE_TEMPERATURE)
    out = parse_judge_response(raw)
    out["usage"] = usage
    out["judge_model"] = C.JUDGE_MODEL
    out["raw"] = raw
    return out


def _seed_tasks():
    return [json.loads(l) for l in open(C.TASKS_JSONL)]


def _orig_console_log(uuid, level):
    return C.GAIA_LEVEL_DIRS[level] / uuid / "0" / "console_log.txt"


def cmd_original():
    for t in _seed_tasks():
        out_dir = C.JUDGED_DIR / t["uuid"]
        out_path = out_dir / "original.json"
        if out_path.exists():
            print("skip (exists):", out_path); continue
        log = _orig_console_log(t["uuid"], t["level"]).read_text(errors="ignore")
        res = judge_trace(log)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(res, indent=1))
        print(f"judged ORIGINAL {t['uuid']} -> success={res['success']} "
              f"modes={[m for m,v in res['modes'].items() if v]} ${res['usage']['cost_usd']:.3f}")


def cmd_runs():
    for t in _seed_tasks():
        for r in range(C.RUNS_PER_TASK):
            tr = C.RUNS_DIR / t["uuid"] / str(r) / "transcript.txt"
            if not tr.exists():
                continue
            out_path = C.JUDGED_DIR / t["uuid"] / f"run_{r}.json"
            if out_path.exists():
                print("skip (exists):", out_path); continue
            res = judge_trace(tr.read_text(errors="ignore"))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(res, indent=1))
            print(f"judged {t['uuid']} run {r} -> success={res['success']} "
                  f"modes={[m for m,v in res['modes'].items() if v]} ${res['usage']['cost_usd']:.3f}")


def cmd_file(path, out):
    res = judge_trace(Path(path).read_text(errors="ignore"))
    print(json.dumps({k: res[k] for k in ("success", "modes", "summary", "usage")}, indent=1))
    if out:
        Path(out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", action="store_true")
    ap.add_argument("--runs", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.original:
        cmd_original()
    elif a.runs:
        cmd_runs()
    elif a.file:
        cmd_file(a.file, a.out)
    else:
        ap.print_help()
