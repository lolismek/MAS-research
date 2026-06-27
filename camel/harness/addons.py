"""AddOnLayer seam for the CAMEL-style pipeline.

Every coordination/memory method (our shared belief board, chatdev/metagpt-style
memory, DOWN, ...) is the SAME interface plugged into an otherwise-fixed pipeline.
A run holds everything constant except the AddOn, so any difference is the layer's.

A linear pipeline only has two places state can flow between agents, so the layer
only needs two hooks:

  - inject_context(role, messages) -> messages
        Called inside run_agent BEFORE the inner loop. Prepend shared state
        (the board, retrieved memory, ...) onto this agent's message list.
        This is the "ctx" from the design sketch: for vanilla it returns the
        messages unchanged, so the only thing crossing an edge is the upstream
        agent's polished output.

  - on_turn_end(role, result) -> None
        Called AFTER an agent finishes its inner loop. Capture / summarize /
        publish (a memory layer writes the agent's sincere state here).

vanilla = both hooks are no-ops. belief_board (next) overrides both: inject the
board, and write the agent's note on turn end.
"""


class AddOn:
    """No-op base == the `vanilla` control arm."""
    name = "vanilla"

    def inject_context(self, role, messages):
        return messages

    def on_turn_end(self, role, result):
        return None


def get_addon(arm: str) -> "AddOn":
    """Resolve an arm name to an AddOn instance. Only `vanilla` exists today;
    belief_board / memory arms register here as they are built."""
    if arm in (None, "vanilla"):
        return AddOn()
    raise ValueError(f"unknown add-on arm {arm!r} (have: vanilla)")
