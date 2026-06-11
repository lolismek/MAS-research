"""A-side prompts: session framing + CORAL-style reflection note request.

The reflection instruction mirrors the structure of CORAL's reflect heartbeat
(coral/hub/prompts/reflect.md: anchor in concrete results, examine surprises,
analyze causes, plan next experiment), compacted to a single note request and
stripped of CORAL-CLI mechanics. The ~150-word cap is what makes the channel
lossy — that is the point of the probe, do not raise it casually.
"""

A_SYSTEM = (
    "You are an autonomous optimization agent. You work in long sessions on an "
    "open-ended optimization task, logging attempts, eval scores, and observations."
)

REFLECT_INSTRUCTION = """\
Pause and reflect on your session. Write a single markdown note (at most 150 words) \
for the shared notes/ directory, so that another agent can pick up your work.

Anchor it in concrete results:
- What specific changes led to score improvements or regressions?
- What surprised you? Surprises reveal gaps in the shared mental model.
- For your most significant result, *why* did it happen?
- What's one specific thing to try next, and what do you expect to happen?

Write only the note text, no preamble."""


def build_a_messages(transcript: str) -> list[dict]:
    return [
        {"role": "system", "content": A_SYSTEM},
        {"role": "user", "content": (
            f"Here is your session log so far:\n\n{transcript}\n\n{REFLECT_INSTRUCTION}"
        )},
    ]
