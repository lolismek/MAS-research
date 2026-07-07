"""The arm seam (P0 stub — only `vanilla` exists yet).

An arm is a policy over exactly two decisions (PLAN "The seam"):
  1. what crosses an edge  (the payload: hand-off note / worker report / message)
  2. what is written to / rendered from the one shared store

P0 needs only `vanilla`: the seamless harness — no store, only the natural artifact
crosses the edge. So the whole seam here is a NO-OP base class. The six real
policies (`full`, `sop`, `down`, `board`, `extract`, `board_inert`) and the belief
ledger land in P2 (store.py + this file), plugging into these same hooks so nothing
in agent.py / relay.py / hub.py changes.

Hook surface (kept minimal and stable so P2 only ADDS behavior):
  inject_context(role, messages) -> messages   # prepend the shared-state block (layer 3)
  on_turn_end(role, result)                     # observe/capture after an agent's loop
  extra_tool_specs(role) -> [schema]            # arm-owned write-tools (board's add_belief)
  run_extra_tool(name, arguments) -> str        # execute one of those
  edge_payload(kind, producer_result, default) -> str   # what actually crosses an edge
  render() -> str                               # the shared-state block, or "" for none
  bind(client, model, usd_budget)               # arms that self-meter reuse the client
"""


class AddOn:
    """No-op seam == the `vanilla` arm. Every hook is inert: no store, the natural
    artifact crosses each edge unchanged, no extra tools, nothing rendered. `vanilla`
    MUST be byte-identical to a harness with no arm at all (asserted by the P2
    prompt-diff audit), which is exactly what an all-no-op AddOn gives."""

    name = "vanilla"

    def bind(self, client, model, usd_budget):
        self.client, self.model, self.usd_budget = client, model, usd_budget

    def inject_context(self, role, messages):
        return messages

    def on_turn_end(self, role, result):
        return None

    def extra_tool_specs(self, role):
        return []

    def run_extra_tool(self, name, arguments):
        return f"ERROR: no such tool {name!r}"

    def edge_payload(self, kind, producer_result, default):
        """`default` is the natural artifact the topology already computed (the
        hand-off note / report / message, truncation-guarded). vanilla passes it
        through untouched."""
        return default

    def render(self):
        return ""


_ARMS = {"vanilla": AddOn}


def get_addon(arm):
    """Instantiate an arm by name. P0 knows only `vanilla`; P2 registers the rest."""
    if arm not in _ARMS:
        raise KeyError(f"unknown arm {arm!r}; have {sorted(_ARMS)}")
    return _ARMS[arm]()
