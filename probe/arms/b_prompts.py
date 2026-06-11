"""B-side prompts: the takeover continuation task.

Design constraint from PROBE_PLAN.md: the latent payload is a transport layer
invisible to agents — B's *visible text must be byte-identical* between arm 1
and arm 2. The injection point is marked with a sentinel that is removed
before tokenization; arm 2 places the latent embeddings there, arm 1 places
nothing. Arm 5 adds the raw session log as ordinary text (a different,
explicitly textual condition — the ceiling control).
"""

# Sentinel split point for latent injection: right after the note block.
# Tokenizing the halves separately costs exactly one token vs the joined text
# ("\n"+"\n" instead of "\n\n", measured with the Qwen3 tokenizer). EVERY arm
# goes through the same split path in run_arms, so the seam is identical
# across conditions and comparisons stay paired.
LATENT_SENTINEL = "⟦LATENT_SLOTS⟧"

B_SYSTEM = (
    "You are an autonomous optimization agent taking over a colleague's work "
    "on a shared open-ended optimization task."
)


def build_b_user(objective: str, note: str, questions: list[str],
                 raw_transcript: str | None = None) -> str:
    qs = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    raw_block = ""
    if raw_transcript is not None:
        raw_block = (
            "\nTheir full raw session log is also available:\n\n"
            f"{raw_transcript}\n"
        )
    return f"""\
You are taking over a colleague's work. The objective: {objective}.

Your colleague left this note before handing off:

---
{note}
---
{LATENT_SENTINEL}{raw_block}
First, answer these questions about your colleague's session as concretely as \
you can — exact names, values, and reasons where possible. If the note does \
not say, give your best guess from whatever context you have.

{qs}

Then write a short plan (under 150 words) for your next attempt."""


def build_b_messages(ctx: dict, note: str, raw_transcript: str | None = None) -> list[dict]:
    questions = [f["question"] for f in ctx["facts"]]
    return [
        {"role": "system", "content": B_SYSTEM},
        {"role": "user", "content": build_b_user(ctx["objective"], note, questions, raw_transcript)},
    ]
