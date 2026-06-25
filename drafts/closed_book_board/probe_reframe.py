#!/usr/bin/env python3
"""Reframed branch-and-ask, per user's correction:
  (1) ONE shared, board-aware system prompt (eval-clean note content rules, verbatim),
      with the TRIGGER made checkpoint-gated so the trunk trace stays clean (no inline posting).
  (2) Mid-trace injection is just the terse 'Should I /post, /revise, or /skip?' — the model
      resolves it from its system prompt + its own reasoning, no verbose pause-question.
Shared system prompt is also what makes KV reuse POSSIBLE (same prefix to the cut point);
this probe uses stateless /completions (no reuse) only to validate the MECHANISM + phrasing.
"""
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

# Note CONTENT rules verbatim from eval-clean tools.py (add_note/revise_note), surfaced as
# /post and /revise commands. TRIGGER is checkpoint-gated so the trunk doesn't post inline.
SYS = (
"You are an agent on a team solving a problem. You share a team scratchpad — a shared THINKING "
"SPACE that your teammates read. You interact with it with three commands:\n\n"
"/post <text> - Append a NEW note. Post whenever you learn or work out something a teammate could "
"use: a fact you established, a value or count you computed (write the ACTUAL number), a partial "
"result, a hypothesis you're testing, a dead-end you hit, or what is blocking you. Write about your "
"OWN reasoning, not as a request to a 'user'. Avoid repeating a note already on the board word-for-word.\n"
"/revise <id> <text> - Revise one of YOUR earlier notes ONLY when that note has become FALSE; "
"otherwise /post a new note (older notes stay visible on purpose).\n"
"/skip - post nothing right now and keep reasoning.\n\n"
"IMPORTANT: Do NOT write /post or /revise inside your reasoning. Reason normally. You will be "
"interrupted at checkpoints DURING your work and asked 'Should I /post, /revise, or /skip?' - only "
"THEN emit exactly one command on one line. The checkpoints are how you 'think out loud' to the team "
"as you work. End with 'FINAL ANSWER: ...'.")

PROBLEM = ("A snail is at the bottom of a 12-foot well. Each day it climbs up 3 feet, but each "
           "night it slides back 2 feet. How many days does it take the snail to get out of the well?")

def split_think(content):
    e = content.find("</think>")
    think = content[:e] if e != -1 else content
    answer = content[e+8:].strip() if e != -1 else ""
    return think.strip(), answer

# ---- 1) Generate the trunk with the SHARED board-aware system prompt ----
r = client.chat.completions.create(model=MODEL, temperature=0, max_tokens=2000,
    messages=[{"role": "system", "content": SYS},
              {"role": "user", "content": PROBLEM}])
think, answer = split_think(r.choices[0].message.content or "")
paras = [p.strip() for p in re.split(r"\n\s*\n", think) if p.strip()]
inline = [p for p in paras if "/post" in p or "/revise" in p or "/skip" in p]
print(f"=== TRUNK TRACE: {len(paras)} paragraphs, {r.usage.completion_tokens} tok ===")
print(f"=== POLLUTION CHECK: {len(inline)} paragraph(s) contain a command inline (want 0) ===")
print(f"=== FINAL ANSWER: {answer[-60:]!r} ===\n")
for i, p in enumerate(paras):
    print(f"  [p{i}] {re.sub(chr(10),' ',p)[:110]}")

# ---- 2) Fork at two cut points; inject the terse question; continue via /completions ----
def raw_prompt(prefix, board):
    boardstr = "\n".join(f"  [{i}] {b}" for i, b in enumerate(board)) or "  (empty)"
    inject = (f"\n\n--- team scratchpad so far ---\n{boardstr}\n--- checkpoint ---\n"
              "Should I /post, /revise, or /skip?\n")
    return (f"<|im_start|>system\n{SYS}<|im_end|>\n"
            f"<|im_start|>user\n{PROBLEM}<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n{prefix}{inject}")

n = len(paras)
cuts = sorted(set([max(1, round(n * f)) for f in (0.45, 0.75)]))
board = []
print(f"\n=== BRANCH-AND-ASK at cut points {cuts} (of {n} paras) ===")
for k in cuts:
    prefix = "\n\n".join(paras[:k])
    rr = client.completions.create(model=MODEL, prompt=raw_prompt(prefix, board),
                                   max_tokens=160, temperature=0)
    out = rr.choices[0].text
    # keep only the first command line the model emits
    cmd = next((l.strip() for l in out.splitlines()
                if l.strip().startswith(("/post", "/revise", "/skip"))), None)
    print(f"\n  >> after {k}/{n} paras  (prefix ends: ...{re.sub(chr(10),' ',prefix)[-80:]!r})")
    print(f"     RAW continuation: {re.sub(chr(10),' ',out)[:240]!r}")
    print(f"     EXTRACTED command: {cmd!r}")
    if cmd and cmd.startswith("/post"):
        board.append(cmd[len("/post"):].strip())
