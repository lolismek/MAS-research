#!/usr/bin/env python3
"""Validate the prefix-replay board idea: generate ONE clean reasoning trace
(no note instruction), then replay growing prefixes of it through the SAME model,
asking at each checkpoint for the reasoner's CURRENT belief + confidence. Tests
whether the reconstructed trajectory (a) is faithful/evolving and (b) what it costs.
Hits Tinker directly to see raw <think>."""
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

PROBLEM = ("A store sells notebooks for $3 each. If you buy 4 or more, you get 25% off the "
           "entire order. Maria has $20. What is the maximum number of notebooks she can buy?")

def clean_then_answer(content):
    e = content.find("</think>")
    return (content[:e] if e != -1 else content, content[e+8:].strip() if e != -1 else "")

# 1) Generate the clean trace (NO note instruction) — the untouched agent reasoning.
r = client.chat.completions.create(model=MODEL, temperature=0, max_tokens=3000,
    messages=[{"role": "system", "content": "Solve the problem, reasoning step by step. End with 'FINAL ANSWER: ...'."},
              {"role": "user", "content": PROBLEM}])
think, answer = clean_then_answer(r.choices[0].message.content or "")
gen_tok = r.usage.completion_tokens
paras = [p.strip() for p in re.split(r"\n\s*\n", think) if p.strip()]
print(f"=== CLEAN TRACE: {len(paras)} paragraphs, {gen_tok} gen tokens, answer={answer!r} ===")
for i, p in enumerate(paras):
    print(f"  [p{i}] {p[:90].replace(chr(10),' ')}")

# 2) Replay ~6 evenly-spaced cumulative prefixes through the SAME model.
OBS = ("You are inspecting another reasoner's chain-of-thought, which may be CUT OFF mid-way. "
       "Based ONLY on the excerpt shown (do not solve the problem yourself, do not use anything "
       "beyond the excerpt), answer in this exact format on one line: "
       "BELIEF: <their current leading answer, or 'none yet'> | DRIVER: <the single consideration "
       "pushing them there right now> | CONF: <0.0-1.0 that this is where their reasoning points>.")

n = len(paras)
cuts = sorted(set([max(1, round(n * f)) for f in (0.15, 0.3, 0.45, 0.6, 0.8, 1.0)]))
print(f"\n=== PREFIX-REPLAY trajectory (checkpoints at paragraphs {cuts}) ===")
replay_tok = 0
for k in cuts:
    prefix = "\n\n".join(paras[:k])
    rr = client.chat.completions.create(model=MODEL, temperature=0, max_tokens=900,
        messages=[{"role": "system", "content": OBS},
                  {"role": "user", "content": f"--- excerpt (first {k} of {n} paragraphs) ---\n{prefix}"}])
    _, note = clean_then_answer(rr.choices[0].message.content or "")
    replay_tok += rr.usage.completion_tokens
    note = re.sub(r"\s+", " ", note).strip() or "(empty / still thinking)"
    print(f"\n  >> after {k}/{n} paragraphs:\n     {note[:300]}")

print(f"\n=== COST: trace={gen_tok} tok | replay={replay_tok} tok over {len(cuts)} checkpoints "
      f"(~{replay_tok//len(cuts)}/checkpoint) | replay/trace ratio={replay_tok/max(gen_tok,1):.1f}x ===")
