"""Closed-book screen: S no-tool samples per task on the relay model. Tasks solved in >= 2 of S
are dropped from the experiment (retrieval not necessary for them).

Output: lip/data/closed_book.jsonl (one line per task: samples, n_correct) and
        lip/data/tasks_screened.jsonl (the kept tasks).
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from llm import TinkerChat, spend
from judge import score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "lip", "data")
S = 3
SYS = ("Answer the question from your own knowledge. Think it through, then end your reply with a single line "
       "of the form:\nFINAL ANSWER: <answer>\nGive exactly one answer, as short as possible (a name, a number, a date, a word).")

def final_answer(text):
    for line in reversed((text or "").splitlines()):
        if "FINAL ANSWER:" in line.upper():
            return line.split(":", 1)[1].strip()
    return (text or "").strip().splitlines()[-1].strip() if (text or "").strip() else ""

def run_task(t, c):
    out = []
    for s in range(S):
        r = c.chat([{"role": "system", "content": SYS}, {"role": "user", "content": t["question"]}],
                   tag=f"cb/{t['id']}/{s}")
        ans = final_answer(r["content"])
        sc = score(t["question"], t["answer"], ans, tag=f"cbj/{t['id']}/{s}")
        out.append(dict(answer=ans, correct=sc["correct"], em=sc["em"], judge=sc["judge"], reason=sc["reason"],
                        finish=r["finish"], completion_tokens=r["completion_tokens"]))
    return dict(id=t["id"], gold=t["answer"], samples=out, n_correct=sum(o["correct"] for o in out))

def main():
    tasks = [json.loads(l) for l in open(os.path.join(DATA, "tasks.jsonl"))]
    outp = os.path.join(DATA, "closed_book.jsonl")
    done = {json.loads(l)["id"] for l in open(outp)} if os.path.exists(outp) else set()
    todo = [t for t in tasks if t["id"] not in done]
    print(f"closed-book: {len(tasks)} tasks, {len(todo)} to run", flush=True)
    c = TinkerChat(max_tokens=6000)
    with ThreadPoolExecutor(8) as ex, open(outp, "a") as f:
        for i, rec in enumerate(ex.map(lambda t: run_task(t, c), todo)):
            f.write(json.dumps(rec) + "\n"); f.flush()
            if (i + 1) % 20 == 0: print(f"  {i+1}/{len(todo)}  spend ${spend('cb'):.3f}", flush=True)
    recs = [json.loads(l) for l in open(outp)]
    keep = {r["id"] for r in recs if r["n_correct"] < 2}
    with open(os.path.join(DATA, "tasks_screened.jsonl"), "w") as f:
        for t in tasks:
            if t["id"] in keep: f.write(json.dumps(t) + "\n")
    from collections import Counter
    print("n_correct distribution:", dict(sorted(Counter(r["n_correct"] for r in recs).items())))
    print(f"kept {len(keep)}/{len(tasks)}  spend ${spend('cb'):.3f}", flush=True)

if __name__ == "__main__":
    main()
