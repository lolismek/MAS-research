#!/usr/bin/env python3
"""Live cost/progress for the macnet-rand batch. Usage: python3 cost.py [tag_substr]"""
import json, sys, time, collections

CALLS = "proxy/calls.jsonl"
want = sys.argv[1] if len(sys.argv) > 1 else "mn_rand"

def load():
    rows = []
    for l in open(CALLS):
        try:
            c = json.loads(l)
        except Exception:
            continue
        if want in c.get("tag", ""):
            rows.append(c)
    return rows

rows = load()
cost = sum(c.get("cost", 0) for c in rows)
ok = [c for c in rows if c.get("finish") == "stop"]
length = [c for c in rows if c.get("finish") == "length"]
errs = [c for c in rows if "error" in c]

by = collections.defaultdict(lambda: [0, 0.0, 0])  # calls, cost, errors
for c in rows:
    b = by[c["tag"]]
    b[0] += 1
    b[1] += c.get("cost", 0)
    if "error" in c:
        b[2] += 1

print(f"=== {want}  @ {time.strftime('%H:%M:%S')} ===")
print(f"total: ${cost:.2f}   {len(rows)} calls   "
      f"stop={len(ok)} length={len(length)} err={len(errs)}")
print("-" * 52)
for tag in sorted(by, key=lambda t: by[t][1], reverse=True):
    n, c, e = by[tag]
    flag = f"  !{e}err" if e else ""
    print(f"  {tag:30s} ${c:6.2f}  {n:3d} calls{flag}")
