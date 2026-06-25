#!/usr/bin/env python3
"""Reframe v2: strip the protocol scaffolding that poisoned v1.
  - System prompt: ONLY the verbatim eval-clean note rules as /post and /revise definitions.
    NO 'you will be interrupted at checkpoints / don't post inline' meta-talk (that made the
    model ruminate about the mechanism and dismiss the injected question as a 'simulation').
  - Injection: terse + DIRECTIVE ('reply with one command'), not a self-question to ruminate on.
Shared system prompt (gen + extraction) => KV reuse stays POSSIBLE; this probe uses /completions."""
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

# ONLY the note CONTENT rules (verbatim eval-clean), surfaced as /post and /revise. No protocol talk.
SYS = (
"Solve the problem, reasoning step by step. End with 'FINAL ANSWER: ...'.\n\n"
"You also keep a shared team scratchpad that teammates read. Two commands operate on it:\n"
"/post <text> - Append a NEW note: a fact you established, a value or count you computed (write the "
"ACTUAL number), a partial result, a hypothesis you're testing, a dead-end you hit, or what is "
"blocking you. Write about your OWN reasoning, not as a request to a 'user'. Don't repeat a note "
"already on the board word-for-word.\n"
"/revise <id> <text> - Revise one of YOUR earlier notes ONLY when it has become FALSE; otherwise "
"/post a new note.")

PROBLEM = ("A snail is at the bottom of a 12-foot well. Each day it climbs up 3 feet, but each "
           "night it slides back 2 feet. How many days does it take the snail to get out of the well?")

def split_think(content):
    e = content.find("</think>")
    return (content[:e] if e != -1 else content).strip(), (content[e+8:].strip() if e != -1 else "")

# ---- 1) Trunk with the shared system prompt ----
r = client.chat.completions.create(model=MODEL, temperature=0, max_tokens=2600,
    messages=[{"role": "system", "content": SYS}, {"role": "user", "content": PROBLEM}])
think, answer = split_think(r.choices[0].message.content or "")
paras = [p.strip() for p in re.split(r"\n\s*\n", think) if p.strip()]
inline = [i for i, p in enumerate(paras) if re.search(r"/post|/revise|/skip", p)]
print(f"=== TRUNK: {len(paras)} paras, {r.usage.completion_tokens} tok | answer={answer[-50:]!r} ===")
print(f"=== POLLUTION: command appears inline in paras {inline} (want []) ===\n")
for i, p in enumerate(paras):
    print(f"  [p{i}] {re.sub(chr(10),' ',p)[:110]}")

# ---- 2) Branch-and-ask: terse, DIRECTIVE injection ----
def raw_prompt(prefix, board):
    boardstr = "\n".join(f"  [{i}] {b}" for i, b in enumerate(board)) or "  (empty)"
    inject = (f"\n\nScratchpad so far:\n{boardstr}\n"
              "Reply with exactly one command for the scratchpad and nothing else: "
              "/post <text>  OR  /revise <id> <text>  OR  /skip\n")
    return (f"<|im_start|>system\n{SYS}<|im_end|>\n<|im_start|>user\n{PROBLEM}<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n{prefix}{inject}")

n = len(paras)
cuts = sorted(set([max(1, round(n * f)) for f in (0.4, 0.65, 0.85)]))
board = []
print(f"\n=== BRANCH-AND-ASK at cuts {cuts} of {n} ===")
for k in cuts:
    prefix = "\n\n".join(paras[:k])
    rr = client.completions.create(model=MODEL, prompt=raw_prompt(prefix, board),
                                   max_tokens=140, temperature=0)
    out = rr.choices[0].text
    cmd = next((l.strip() for l in out.splitlines()
                if l.strip().startswith(("/post", "/revise", "/skip"))), None)
    print(f"\n  >> after {k}/{n}  (ends: ...{re.sub(chr(10),' ',prefix)[-75:]!r})")
    print(f"     RAW: {re.sub(chr(10),' ',out)[:200]!r}")
    print(f"     CMD: {cmd!r}")
    if cmd and cmd.startswith("/post"):
        board.append(cmd[len("/post"):].strip())

print(f"\n=== RECONSTRUCTED BOARD ({len(board)} notes) ===")
for i, b in enumerate(board):
    print(f"  [{i}] {b}")
