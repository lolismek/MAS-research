"""Belief ledger — verbatim port of duet's store.BeliefLedger (+ the observer
line parser used by the `extract` arm). The ledger is the manipulated
representation of the board/extract arms: attributed, revisable entries
{id, author, object, belief, confidence, status}, never deleted."""
import re


class BeliefLedger:
    def __init__(self):
        self.entries = []

    def add(self, author, obj, belief, confidence, kind="belief"):
        e = dict(id=f"b{len(self.entries) + 1}", author=author, object=(obj or "").strip(),
                 belief=(belief or "").strip(), confidence=_clamp(confidence),
                 kind=("observation" if kind == "observation" else "belief"),
                 status="active", revises=None)
        self.entries.append(e)
        return e

    def revise(self, author, belief_id, belief=None, confidence=None, status=None):
        old = next((e for e in self.entries if e["id"] == belief_id), None)
        if old is None:
            return None
        if status == "retracted" and not belief:
            old["status"] = "retracted"
            old["retracted_by"] = author
            return old
        old["status"] = "revised"
        e = dict(id=f"b{len(self.entries) + 1}", author=author, object=old["object"],
                 belief=(belief or old["belief"]).strip(),
                 confidence=_clamp(confidence if confidence is not None else old["confidence"]),
                 kind=old.get("kind", "belief"), status="active", revises=belief_id)
        self.entries.append(e)
        return e

    def active(self):
        return [e for e in self.entries if e["status"] == "active"]

    def render(self):
        if not self.entries:
            return ""
        lines = []
        for e in self.entries:
            head = f"[{e['id']} · {e['author']}]"
            if e["status"] == "active":
                rev = f" (revises {e['revises']})" if e["revises"] else ""
                lead = "observed — " if e.get("kind") == "observation" else ""
                lines.append(f"{head} {lead}{e['object']}: {e['belief']} "
                             f"(confidence {e['confidence']:.2f}){rev}")
            elif e["status"] == "retracted":
                lines.append(f"{head} {e['object']}: RETRACTED by {e.get('retracted_by', '?')} "
                             f"— was: {e['belief']}")
            else:
                lines.append(f"{head} {e['object']}: superseded — was: {e['belief']}")
        return "Beliefs recorded so far (id · author):\n" + "\n".join(lines)

    def to_json(self):
        return list(self.entries)

    @classmethod
    def from_json(cls, entries):
        led = cls()
        led.entries = list(entries or [])
        return led


def _clamp(c):
    try:
        return max(0.0, min(1.0, float(c)))
    except (TypeError, ValueError):
        return 0.5


_BELIEF_LINE = re.compile(r"^\s*(OBSERVATION|BELIEF)\s*:\s*(.+?)\s*$", re.M | re.I)


def parse_belief_lines(text):
    out = []
    for tok, body in _BELIEF_LINE.findall(text or ""):
        if body.strip().lower() == "none":
            continue
        kind = "observation" if tok.upper() == "OBSERVATION" else "belief"
        parts = [p.strip() for p in body.split("|")]
        if len(parts) >= 3:
            obj, belief, conf = parts[0], " | ".join(parts[1:-1]), parts[-1]
        elif len(parts) == 2:
            obj, belief, conf = parts[0], parts[1], "0.5"
        else:
            obj, belief, conf = "task", parts[0], "0.5"
        if belief:
            out.append((kind, obj, belief, _clamp(_first_float(conf))))
    return out


def _first_float(s):
    m = re.search(r"[0-9.]+", s or "")
    return m.group(0) if m else "0.5"
