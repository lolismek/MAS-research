"""Per-atom judge for the two-atom internal-belief arms (int2_*): one gpt-oss-120b call per run that reads every handoff
and the final answer and says, for each atom, (a) which handoffs convey it and (b) whether the final answer follows it.
Writes tr["atom_judge"] = {"A": {"handoffs": [agent, ...], "final": "yes"|"no"|"unclear"}, "B": {...}, "reading": ...}
into run.json. Skips runs that already have it (unless --redo). Tags: judge/int2_atoms/<arm>/<task>/r<run>.

  python lip/internal/atom_judge.py --arms int2_none int2_both1 int2_split13 int2_all --workers 12
"""
import argparse, glob, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
from llm import TinkerChat, BudgetExceeded
from run_task import TRACES, DATA, load_tasks

MODEL = "openai/gpt-oss-120b"
SYS = """You analyse a relay of agents answering a factual question. The question the agents saw had two qualifiers removed
(atoms A and B). Some agents privately knew one or both atoms; you see only the messages they passed and the final answer.

For EACH atom decide:
1. "handoffs": the agent numbers whose handoff message conveys that atom's constraint (states it, or clearly acts on it,
   e.g. names the specific year/ordinal/entity/scope the atom points to). Empty list if none.
2. "final": does the final answer follow the atom's reading? "yes" if it matches the gold answer or the reference answer
   for a reading that includes this atom, "no" if it matches a reading without this atom or clearly ignores the constraint,
   "unclear" if you cannot tell. Use the reference answers; they are approximate (closed-book).
Then "reading": which reading the final answer reflects: "both", "A_only", "B_only", "neither", or "other" (wrong for
another reason, or cannot tell).

Reply with JSON only:
{"A": {"handoffs": [..], "final": "yes"|"no"|"unclear"}, "B": {"handoffs": [..], "final": "yes"|"no"|"unclear"},
 "reading": "both"|"A_only"|"B_only"|"neither"|"other", "reason": "<one short sentence>"}"""

def prompt(t, tr):
    A, B = t["atoms"]; ref = t.get("ref") or {}
    hs = "\n\n".join(f"--- handoff from agent {a['agent']} ---\n{(a.get('handoff') or '(empty)')[:3000]}"
                     for a in tr["agents"] if a.get("handoff") is not None)
    return (f"Original question: {t['original_question']}\nQuestion the agents saw: {t['question']}\n\n"
            f"Atom A (removed: {A['qualifier']!r}): {A['belief']}\nAtom B (removed: {B['qualifier']!r}): {B['belief']}\n\n"
            f"Gold answer (both atoms): {t['answer']}\nReference answers (approximate): A only (B ignored): {ref.get('A_only')}; "
            f"B only (A ignored): {ref.get('B_only')}; neither: {ref.get('neither')}\n\n"
            f"Handoff messages:\n{hs or '(none)'}\n\nFinal answer (agent {tr.get('finished_by')}): {tr.get('final')}\n"
            f"(graded against gold: {'correct' if tr.get('correct') else 'incorrect'})\n\nJSON:")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True); ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--tasks", default=os.path.join(DATA, "tasks_internal_2atom.jsonl")); ap.add_argument("--redo", action="store_true")
    a = ap.parse_args(); tasks = load_tasks(a.tasks)
    chat = TinkerChat(model=MODEL, max_tokens=3000, timeout=150)
    paths = [p for arm in a.arms for p in sorted(glob.glob(os.path.join(TRACES, arm, "*", "run_*", "run.json")))]
    def job(p):
        tr = json.load(open(p))
        if not tr.get("agents") or tr.get("error") or (tr.get("atom_judge") and not a.redo): return "skip"
        t = tasks[tr["task_id"]]
        try:
            r = chat.chat([dict(role="system", content=SYS), dict(role="user", content=prompt(t, tr))],
                          tag=f"judge/int2_atoms/{tr['arm']}/{tr['task_id']}/r{tr['run']}", temperature=0)
        except BudgetExceeded: return "budget"
        except Exception as e: return f"error"
        m = re.search(r"\{.*\}", r["content"] or "", re.S)
        try: j = json.loads(m.group(0))
        except Exception: return "unparsed"
        tr["atom_judge"] = j; json.dump(tr, open(p, "w"), indent=1, ensure_ascii=False)
        return "ok"
    from collections import Counter
    with ThreadPoolExecutor(a.workers) as ex: c = Counter(ex.map(job, paths))
    print(dict(c))

if __name__ == "__main__":
    main()
