#!/usr/bin/env python3
"""Reframe v3: resolve the pollution-vs-KV-reuse tension.
  - Generation system prompt is NEUTRAL (no board words) => clean trunk, no inline planning,
    and the cached prefix [neutral-sys][user][trace] is reusable verbatim.
  - The note RULES are injected AT THE CUT POINT (inside the assistant trace), not at token 0.
    KV reuse needs a shared PREFIX; the divergence is now at the cut, exactly where the fork is.
So: clean trunk + KV-reuse-compatible + rules present when needed. (/completions here; no reuse,
just validating mechanism + faithfulness, incl. a cut placed INSIDE a dead-end if one exists.)"""
import os, re
from openai import OpenAI

for path in ["/Users/alexjerpelea/.superset/worktrees/ec13f4a5-e2f8-42ae-9d29-8076a6319e5b/multi-benchmark-eval/.env"]:
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

client = OpenAI(api_key=os.environ["TINKER_API_KEY"],
                base_url="https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1")
MODEL = "Qwen/Qwen3.6-35B-A3B"

S_NEUTRAL = "Solve the problem, reasoning step by step. End with 'FINAL ANSWER: ...'."

# Verbatim eval-clean note content, injected ONLY at the cut (not in the system prompt).
NOTE_RULES = (
"/post <text> - append a NEW note to the team scratchpad: a fact you established, a value or count "
"you computed (write the ACTUAL number), a partial result, a hypothesis you're testing, a dead-end "
"you hit, or what is blocking you. Your OWN reasoning, not a request to a 'user'. Don't repeat an "
"existing note word-for-word.\n"
"/revise <id> <text> - revise one of YOUR notes ONLY when it has become FALSE.")

PROBLEM = ("A snail is at the bottom of a 12-foot well. Each day it climbs up 3 feet, but each "
           "night it slides back 2 feet. How many days does it take the snail to get out of the well?")

def split_think(content):
    e = content.find("</think>")
    return (content[:e] if e != -1 else content).strip(), (content[e+8:].strip() if e != -1 else "")

# ---- 1) Clean neutral trunk ----
r = client.chat.completions.create(model=MODEL, temperature=0, max_tokens=2600,
    messages=[{"role": "system", "content": S_NEUTRAL}, {"role": "user", "content": PROBLEM}])
think, answer = split_think(r.choices[0].message.content or "")
paras = [p.strip() for p in re.split(r"\n\s*\n", think) if p.strip()]
pollution = [i for i, p in enumerate(paras) if re.search(r"/post|/revise|scratchpad|teammate", p, re.I)]
backtracks = [i for i, p in enumerate(paras)
              if re.search(r"\bwait\b|mistake|let me reconsider|i was wrong|actually,|hmm", p, re.I)]
print(f"=== NEUTRAL TRUNK: {len(paras)} paras, {r.usage.completion_tokens} tok | answer={answer[:60]!r} ===")
print(f"=== POLLUTION: board words in paras {pollution} (want []) | BACKTRACKS at paras {backtracks} ===\n")
for i, p in enumerate(paras):
    mark = " <-- BACKTRACK" if i in backtracks else ""
    print(f"  [p{i}] {re.sub(chr(10),' ',p)[:104]}{mark}")

# ---- 2) Branch-and-ask: rules injected AT the cut. Place a cut right at a dead-end if present. ----
def raw_prompt(prefix, board):
    boardstr = "\n".join(f"  [{i}] {b}" for i, b in enumerate(board)) or "  (empty)"
    inject = (f"\n\n[Pause for a team scratchpad note.\n{NOTE_RULES}\nScratchpad so far:\n{boardstr}\n"
              "Reply with exactly one command and nothing else: /post <text> OR /revise <id> <text> OR /skip]\n")
    return (f"<|im_start|>system\n{S_NEUTRAL}<|im_end|>\n<|im_start|>user\n{PROBLEM}<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n{prefix}{inject}")

n = len(paras)
cuts = sorted(set([max(1, round(n * f)) for f in (0.3, 0.55, 0.8)] + [b + 1 for b in backtracks[:1]]))
board = []
print(f"\n=== BRANCH-AND-ASK at cuts {cuts} of {n} (rules injected at cut) ===")
for k in cuts:
    prefix = "\n\n".join(paras[:k])
    rr = client.completions.create(model=MODEL, prompt=raw_prompt(prefix, board),
                                   max_tokens=140, temperature=0)
    out = rr.choices[0].text
    cmd = next((l.strip() for l in out.splitlines()
                if l.strip().startswith(("/post", "/revise", "/skip"))), None)
    dead = " (cut AT a backtrack)" if k - 1 in backtracks else ""
    print(f"\n  >> after {k}/{n}{dead}  (ends: ...{re.sub(chr(10),' ',prefix)[-72:]!r})")
    print(f"     CMD: {cmd!r}")
    if cmd and cmd.startswith("/post"):
        board.append(cmd[len("/post"):].strip())

print(f"\n=== RECONSTRUCTED BOARD ({len(board)} notes) ===")
for i, b in enumerate(board):
    print(f"  [{i}] {b[:200]}")
