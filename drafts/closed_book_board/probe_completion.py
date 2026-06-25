#!/usr/bin/env python3
"""Can Tinker CONTINUE a partial generation (prefill), not just answer a chat turn?
Tests three ways: (A) raw /completions endpoint, (B) chat assistant-prefill via
continue_final_message, (C) the real idea: continue a partial <think> trace with an
injected 'save a note?' question. If continuation works, the note is grounded in the
ACTUAL reasoning state (no re-solving)."""
import os
from openai import OpenAI

for path in ["/Users/alexjerpelea/.superset/worktrees/ec13f4a5-e2f8-42ae-9d29-8076a6319e5b/multi-benchmark-eval/.env"]:
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

client = OpenAI(api_key=os.environ["TINKER_API_KEY"],
                base_url="https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1")
MODEL = "Qwen/Qwen3.6-35B-A3B"

print("=== A) raw /v1/completions (full control over the prefix text) ===")
try:
    r = client.completions.create(model=MODEL, prompt="The first three prime numbers are 2, 3,",
                                  max_tokens=12, temperature=0)
    print("  OK ->", repr(r.choices[0].text))
except Exception as e:
    print("  FAIL ->", type(e).__name__, str(e)[:220])

print("\n=== B) chat assistant-prefill via continue_final_message ===")
try:
    r = client.chat.completions.create(model=MODEL, max_tokens=20, temperature=0,
        messages=[{"role": "user", "content": "Continue counting from where I stop: one, two,"},
                  {"role": "assistant", "content": "three, four,"}],
        extra_body={"add_generation_prompt": False, "continue_final_message": True})
    print("  OK -> continuation:", repr(r.choices[0].message.content))
except Exception as e:
    print("  FAIL ->", type(e).__name__, str(e)[:220])

print("\n=== C) THE IDEA: continue a partial <think> with an injected note question ===")
# A clean partial reasoning trace, cut mid-think, with the injected introspection prompt.
PARTIAL = (
"<|im_start|>user\nA snail climbs a 12-foot well: +3 ft each day, -2 ft each night. "
"How many days to escape?<|im_end|>\n<|im_start|>assistant\n<think>\n"
"Let me work the net progress. Each full day-night cycle nets +1 ft. Naively 12 cycles, "
"but the last climb matters: once it reaches the top during the day it's out, no slide back. "
"So I need the day it first touches 12 during the climb.\n\n"
"[Pause] Is this a good moment to stop and save a scratchpad note for my teammates? "
"If yes, write it as NOTE: <text>. If not, reply NO and keep thinking.\n")
try:
    r = client.completions.create(model=MODEL, prompt=PARTIAL, max_tokens=160, temperature=0)
    print("  continuation ->", repr(r.choices[0].text[:400]))
except Exception as e:
    print("  (raw path) FAIL ->", type(e).__name__, str(e)[:160])
