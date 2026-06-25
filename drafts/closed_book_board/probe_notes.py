#!/usr/bin/env python3
"""Test whether Qwen3.6-35B-A3B can be prompted to interleave [NOTE]...[/NOTE]
belief markers WITHIN its <think> trace (live, not bunched at the end), without
breaking the reasoning. Hits Tinker DIRECTLY (not our proxy) so we see the raw
<think> block. Three calls: (1) multi-step w/ a turning point, (2) under-specified
question -> does a note capture honest uncertainty, (3) control (no note instr)."""
import os, re
from openai import OpenAI

for path in ["/Users/alexjerpelea/.superset/worktrees/ec13f4a5-e2f8-42ae-9d29-8076a6319e5b/multi-benchmark-eval/.env"]:
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

client = OpenAI(api_key=os.environ["TINKER_API_KEY"],
                base_url="https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1")
MODEL = "Qwen/Qwen3.6-35B-A3B"

NOTE_SYS = (
    "Solve the problem, reasoning step by step. CRITICAL INSTRUCTION ABOUT YOUR REASONING: "
    "as you think, interleave short belief notes written as [NOTE]...[/NOTE] directly inside "
    "your reasoning, AT THE MOMENT each thought occurs (not collected at the end). Each note = "
    "one sentence stating your CURRENT best answer/hypothesis and the single consideration "
    "driving it right now. Write one when you first read the problem, again at any turning point "
    "where you change your mind, and once just before you commit. Be honest in the notes: if you "
    "are unsure or lack information, say so in the note. After reasoning, end with 'FINAL ANSWER: ...'."
)

P_MULTISTEP = ("A store sells notebooks for $3 each. If you buy 4 or more, you get 25% off the "
               "entire order. Maria has $20. What is the maximum number of notebooks she can buy?")
P_UNDERSPEC = ("A train leaves Chicago heading west at 60 miles per hour. What time does it "
               "arrive in Denver?")


def parse_notes(content):
    """Return (think_text, answer_text, [(start_offset, in_think, text), ...])."""
    end = content.find("</think>")
    think = content[:end] if end != -1 else content
    answer = content[end + len("</think>"):] if end != -1 else ""
    notes = []
    # tolerant: [NOTE]...[/NOTE], or [NOTE]... up to next [NOTE]/</think>/end
    for m in re.finditer(r"\[NOTE\](.*?)(?:\[/NOTE\]|(?=\[NOTE\])|</think>|$)", content, re.DOTALL):
        notes.append((m.start(), end == -1 or m.start() < end, m.group(1).strip()[:200]))
    return think, answer, end != -1, notes


def run(label, sys_prompt, user_prompt):
    r = client.chat.completions.create(
        model=MODEL, max_tokens=3000, temperature=0,
        messages=([{"role": "system", "content": sys_prompt}] if sys_prompt else [])
                 + [{"role": "user", "content": user_prompt}])
    ch = r.choices[0]
    content = ch.message.content or ""
    think, answer, closed, notes = parse_notes(content)
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    print(f"finish_reason={ch.finish_reason}  completion_tokens={r.usage.completion_tokens}  "
          f"think_closed={closed}  think_len={len(think)}  answer_len={len(answer)}")
    n_in_think = sum(1 for _, t, _ in notes if t)
    print(f"notes: {len(notes)} total, {n_in_think} INSIDE <think>, {len(notes)-n_in_think} in answer")
    for off, in_think, txt in notes:
        frac = off / max(len(think), 1)
        loc = f"think @ {frac:0.2f}" if in_think else "ANSWER"
        print(f"  - [{loc}] {txt}")
    print(f"--- answer tail: {answer.strip()[-200:]!r}")
    return content


c1 = run("1. MULTI-STEP (turning point) + note instruction", NOTE_SYS, P_MULTISTEP)
c2 = run("2. UNDER-SPECIFIED (honesty) + note instruction", NOTE_SYS, P_UNDERSPEC)
c3 = run("3. CONTROL multi-step, NO note instruction",
         "Solve the problem, reasoning step by step. End with 'FINAL ANSWER: ...'.", P_MULTISTEP)

print(f"\n\n===== FULL RAW OUTPUT of call 1 (to eyeball interleaving) =====\n{c1[:2600]}")
