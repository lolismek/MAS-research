#!/usr/bin/env python3
"""Prefix-replay board reconstruction, v2: drive the second model with the EXACT
eval-clean add_note/revise_note instructions (tools.py), not a made-up answer-tracker.
Generate one clean trace, then walk its paragraphs; at each, the reader sees the
reasoning-so-far + the board-so-far and decides what note(s) to add/revise per the rule."""
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

# A problem with a genuine dead-end / revision (initial plausible approach is wrong).
PROBLEM = ("A snail is at the bottom of a 12-foot well. Each day it climbs up 3 feet, but each "
           "night it slides back 2 feet. How many days does it take the snail to get out of the well?")

# VERBATIM from tools.py make_board_tools (add_note + revise_note docstrings).
NOTE_RULE = (
"You maintain a shared team scratchpad. The rules for it are EXACTLY:\n\n"
"add_note: Append a NEW note to your slice of the shared team scratchpad. The scratchpad is the "
"team's shared THINKING SPACE, read by your teammates. Use it generously: add a note whenever you "
"learn or work out something a teammate could use - a fact you established, a value or count you "
"computed (write the ACTUAL number), a partial result, a hypothesis you're testing, a dead-end you "
"hit, or what is blocking you. Think out loud AS YOU WORK; don't wait for final conclusions. Write "
"about your OWN reasoning, not as a request to a 'user'. Avoid repeating a note already on the board "
"word-for-word.\n"
"revise_note: Revise one of your earlier notes ONLY when that note has become FALSE; otherwise add a "
"new note (older notes stay visible on purpose).")

def clean(content):
    e = content.find("</think>")
    return content[e+8:].strip() if e != -1 else content.strip()

# 1) clean untouched trace
r = client.chat.completions.create(model=MODEL, temperature=0, max_tokens=3000,
    messages=[{"role": "system", "content": "Solve the problem, reasoning step by step. End with 'FINAL ANSWER: ...'."},
              {"role": "user", "content": PROBLEM}])
full = r.choices[0].message.content or ""
e = full.find("</think>"); think = full[:e] if e != -1 else full
paras = [p.strip() for p in re.split(r"\n\s*\n", think) if p.strip()]
print(f"=== CLEAN TRACE: {len(paras)} paragraphs, {r.usage.completion_tokens} tok, final={clean(full)[-80:]!r} ===")
for i, p in enumerate(paras):
    print(f"  [p{i}] {re.sub(chr(10),' ',p)[:100]}")

# 2) walk paragraphs; reader emits board operations per the verbatim rule
board, replay_tok = [], 0
cuts = list(range(1, len(paras)))  # one checkpoint per new paragraph (skip intro p0)
print(f"\n=== PREFIX-REPLAY with REAL note rules ({len(cuts)} checkpoints) ===")
for k in cuts:
    prefix = "\n\n".join(paras[:k+1])
    boardstr = "\n".join(f"  {b}" for b in board) or "  (empty)"
    sys = (NOTE_RULE + "\n\nBelow is YOUR reasoning so far on a problem, and the notes already on "
           "YOUR scratchpad. Output ONLY the note operations to perform NOW for what the latest "
           "reasoning established, each on its own line as 'ADD: <note text>' or 'REVISE <existing "
           "note text> -> <new text>'. If nothing new is worth a note, output exactly 'NONE'. "
           "Do not solve ahead; only note what the reasoning so far has established.")
    rr = client.chat.completions.create(model=MODEL, temperature=0, max_tokens=1600,
        messages=[{"role": "system", "content": sys},
                  {"role": "user", "content": f"--- your reasoning so far ---\n{prefix}\n\n--- notes already on your scratchpad ---\n{boardstr}"}])
    replay_tok += rr.usage.completion_tokens
    out = clean(rr.choices[0].message.content or "")
    ops = [l.strip() for l in out.splitlines() if l.strip().startswith(("ADD:", "REVISE"))]
    for op in ops:
        if op.startswith("ADD:"):
            board.append(op[4:].strip())
    label = re.sub(r"\s+", " ", out)[:240] if out else "(empty)"
    print(f"\n  >> after p{k}: {label}")

print(f"\n=== FINAL RECONSTRUCTED BOARD ({len(board)} notes) ===")
for b in board:
    print(f"  - {b}")
print(f"\n=== COST: replay={replay_tok} tok / {len(cuts)} checkpoints (~{replay_tok//max(len(cuts),1)} ea) ===")
