"""B-side prompts: the takeover continuation task.

Design constraint from PROBE_PLAN.md: the latent payload is a transport layer
invisible to agents — B's *visible text must be byte-identical* between arm 1
and arm 2. The injection point is marked with a sentinel that is removed
before tokenization; arm 2 places the latent embeddings there, arm 1 places
nothing. Arm 5 adds the raw session log as ordinary text (a different,
explicitly textual condition — the ceiling control).

In-place arms (0 / 2i / 3i / 4i): the sentinel sits where the note text would
be, inside the same fences — the scaffold is byte-identical across the whole
in-place family, and differs from arm 1 only by the note text's removal
(plan §in-place-arms). The alongside rendering is untouched, so outputs stay
comparable with the 2026-06-11 main run.
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
                 raw_transcript: str | None = None, inplace: bool = False) -> str:
    qs = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    raw_block = ""
    if raw_transcript is not None:
        raw_block = (
            "\nTheir full raw session log is also available:\n\n"
            f"{raw_transcript}\n"
        )
    if inplace:
        note_section = f"---\n{LATENT_SENTINEL}\n---{raw_block}"
    else:
        note_section = f"---\n{note}\n---\n{LATENT_SENTINEL}{raw_block}"
    return f"""\
You are taking over a colleague's work. The objective: {objective}.

Your colleague left this note before handing off:

{note_section}
First, answer these questions about your colleague's session as concretely as \
you can — exact names, values, and reasons where possible. If the note does \
not say, give your best guess from whatever context you have.

{qs}

Then write a short plan (under 150 words) for your next attempt."""


def build_b_messages(ctx: dict, note: str, raw_transcript: str | None = None,
                     inplace: bool = False) -> list[dict]:
    questions = [f["question"] for f in ctx["facts"]]
    return [
        {"role": "system", "content": B_SYSTEM},
        {"role": "user", "content": build_b_user(ctx["objective"], note, questions,
                                                 raw_transcript, inplace=inplace)},
    ]
