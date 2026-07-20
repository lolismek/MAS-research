"""Auto-computable probe labels from a frozen phase-1 trajectory.

Per-turn labels ("as of the end of assistant turn t") let every captured
end-of-turn position be a training sample:
  located_file  A has, by this turn, opened/edited/grepped the gold defect
                file (its path appeared in one of A's own tool calls)
  seen_func     the gold function's name has appeared in A's context so far
                (tool call, tool result, or A's own text)
Final-state-only label (one sample per trajectory, at the last position):
  solved        A's end state passes the tests (meta post_A_solved)

These are transcript-derivable on purpose (v1): the probes then measure
whether A's residual stream ENCODES them at canonical positions — the
methodological bar of 2402.18496/2310.02207 — not whether they are secret.
Label leak control: disjoint-by-repo train/eval split + shuffled-probe arm.
"""


def _gold_file_rel(instance):
    return instance["pyfile_path"].split("test_repo/")[1]


def turn_labels(events, instance):
    """List of per-assistant-turn dicts {located_file, seen_func}, one entry
    per assistant event, cumulative."""
    rel = _gold_file_rel(instance)
    base = rel.split("/")[-1]
    fm = str(instance["fm_name"])
    located = False
    seen = False
    out = []
    for ev in events:
        t = ev.get("type")
        if t == "assistant":
            blob = (ev.get("content") or "") + " ".join(
                (c.get("arguments") or "") for c in ev.get("tool_calls", []))
            if rel in blob or base in blob:
                located = True
            if fm in blob:
                seen = True
            out.append({"located_file": located, "seen_func": seen})
        elif t in ("tool", "extra_tool"):
            blob = str(ev.get("arguments", "")) + (ev.get("result") or "")
            if rel in blob or base in blob:
                located = True
            if fm in blob:
                seen = True
            if out:
                out[-1] = {"located_file": located, "seen_func": seen}
    return out


def final_labels(events, meta, instance):
    per_turn = turn_labels(events, instance)
    last = per_turn[-1] if per_turn else {"located_file": False,
                                          "seen_func": False}
    return {"solved": bool(meta.get("post_A_solved")), **last}
