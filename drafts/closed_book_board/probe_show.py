#!/usr/bin/env python3
"""ONE clean end-to-end demo: generate a thinking trace, cut it in the middle, insert the
note-question, continue. Prints the original thinking, the exact cut point, the exact inserted
text, and the model's output — so the whole 'insert in the middle' mechanic is visible."""
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
NOTE_RULES = (
"/post <text> - append a NEW note to the team scratchpad: a fact you established, a value or count "
"you computed (write the ACTUAL number), a partial result, a hypothesis you're testing, a dead-end "
"you hit, or what is blocking you. Your OWN reasoning, not a request to a 'user'. Don't repeat an "
"existing note word-for-word.\n"
"/revise <id> <text> - revise one of YOUR notes ONLY when it has become FALSE.")
PROBLEM = ("A snail is at the bottom of a 12-foot well. Each day it climbs up 3 feet, but each "
           "night it slides back 2 feet. How many days does it take the snail to get out of the well?")

def split_think(c):
    e = c.find("</think>")
    return (c[:e] if e != -1 else c).strip(), (c[e+8:].strip() if e != -1 else "")

# 1) original clean thinking
r = client.chat.completions.create(model=MODEL, temperature=0, max_tokens=2600,
    messages=[{"role": "system", "content": S_NEUTRAL}, {"role": "user", "content": PROBLEM}])
think, answer = split_think(r.choices[0].message.content or "")
paras = [p.strip() for p in re.split(r"\n\s*\n", think) if p.strip()]

print("#" * 78)
print("# PROBLEM:", PROBLEM)
print("#" * 78)
print("\n----- THE MODEL'S ORIGINAL THINKING (its private chain of thought) -----\n")
print(think)
print(f"\n[the model's final answer was: {answer[:80]!r}]")

# 2) cut in the middle
K = max(1, round(len(paras) * 0.4))
prefix = "\n\n".join(paras[:K])
INSERT = (f"\n\n[Pause for a team scratchpad note.\n{NOTE_RULES}\nScratchpad so far:\n  (empty)\n"
          "Reply with exactly one command and nothing else: /post <text> OR /revise <id> <text> OR /skip]\n")

print("\n" + "#" * 78)
print(f"# I CUT THE THINKING AFTER PARAGRAPH {K} OF {len(paras)}. Everything above the cut is")
print("# the model's REAL thinking; below is the text I INSERT at the cut, then I let it continue.")
print("#" * 78)
print("\n----- WHAT THE MODEL NOW SEES (its own thinking up to the cut + my inserted block) -----\n")
print(prefix)
print("\n>>>>>>>>>> vvv INSERTED BY ME vvv >>>>>>>>>>")
print(INSERT.rstrip())
print("<<<<<<<<<< ^^^ INSERTED BY ME ^^^ <<<<<<<<<<")

# 3) continue from exactly that
full_prompt = (f"<|im_start|>system\n{S_NEUTRAL}<|im_end|>\n<|im_start|>user\n{PROBLEM}<|im_end|>\n"
               f"<|im_start|>assistant\n<think>\n{prefix}{INSERT}")
rr = client.completions.create(model=MODEL, prompt=full_prompt, max_tokens=160, temperature=0)
out = rr.choices[0].text

print("\n----- WHAT THE MODEL WROTE BACK (this is the note it chose to post) -----\n")
print(out)
