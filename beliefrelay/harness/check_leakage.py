"""Belief leakage check: no authored belief may contain the task's answer.

Numeric rule: any number appearing in the expected answer must not appear in the
belief text (whole-token match). String rule: the normalized expected answer must not
be a substring of the normalized belief. Also enforces structure: every pool task has
exactly 3 sets x 3 beliefs, all non-empty strings.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    tasks = {json.loads(l)["id"]: json.loads(l)
             for l in open(os.path.join(ROOT, "data", "tasks.jsonl"))}
    pool = json.load(open(os.path.join(ROOT, "pool.json")))
    beliefs = json.load(open(os.path.join(ROOT, "beliefs.json")))
    problems = []
    for p in pool:
        tid = p["task_id"]
        sets = beliefs.get(tid)
        if not sets or len(sets) != 3 or any(len(s) != 3 for s in sets):
            problems.append(f"{tid}: bad structure")
            continue
        exp = tasks[tid]["expected_answer"]
        exp_norm = re.sub(r"\s+", "", exp.lower())
        nums = set(re.findall(r"-?\d+\.?\d*", exp))
        for si, s in enumerate(sets):
            for bi, b in enumerate(s):
                if not isinstance(b, str) or len(b.strip()) < 15:
                    problems.append(f"{tid} set{si} b{bi}: empty/too short")
                    continue
                b_norm = re.sub(r"\s+", "", b.lower())
                if len(exp_norm) >= 2 and exp_norm in b_norm:
                    problems.append(f"{tid} set{si} b{bi}: contains answer string {exp!r}")
                for n in nums:
                    if re.search(rf"(?<![\d.]){re.escape(n)}(?![\d.])", b):
                        problems.append(f"{tid} set{si} b{bi}: contains answer number {n}")
    if problems:
        print(f"LEAKAGE CHECK FAILED ({len(problems)}):")
        for p in problems:
            print(" ", p)
        raise SystemExit(1)
    print(f"leakage check PASS: {len(pool)} tasks x 9 beliefs clean")


if __name__ == "__main__":
    main()
