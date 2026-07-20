"""The one shared store: a belief ledger. Written by A's tools (board), or by
the observer (extract); rendered into B's payload — never both writers at once.

Entries carry `kind` ('belief' | 'observation'): the duet/macnet two-category
typing. Board entries are always 'belief' (A externalizing its own state);
extract's observer types each line itself.
"""
import json
import re


class BeliefLedger:
    def __init__(self):
        self.entries = []          # {id, author, kind, text, confidence, revised}

    def add(self, author, text, confidence=None, kind="belief"):
        e = {"id": len(self.entries) + 1, "author": author, "kind": kind,
             "text": (text or "").strip(), "confidence": confidence, "revised": False}
        self.entries.append(e)
        return e["id"]

    def revise(self, entry_id, text):
        for e in self.entries:
            if e["id"] == entry_id:
                e["text"] = (text or "").strip()
                e["revised"] = True
                return True
        return False

    def render(self, title):
        if not self.entries:
            return ""
        lines = [title]
        for e in self.entries:
            conf = f" (confidence: {e['confidence']})" if e["confidence"] is not None else ""
            rev = " [revised]" if e["revised"] else ""
            tag = "observed — " if e["kind"] == "observation" else ""
            lines.append(f"  {e['id']}. {tag}{e['text']}{conf}{rev}")
        return "\n".join(lines)

    def as_json(self):
        return json.dumps({"entries": self.entries}, indent=2)


_LINE_RE = re.compile(r"^\s*(?:[-*\d.)\s]*)\s*(BELIEF|OBSERVATION)\s*:\s*(.+?)\s*$",
                      re.IGNORECASE)


def parse_typed_lines(text):
    """Parse the observer's output: lines 'BELIEF: ...' / 'OBSERVATION: ...'.
    Anything else is ignored (the observer is prompted to emit only these)."""
    out = []
    for line in (text or "").splitlines():
        m = _LINE_RE.match(line)
        if m:
            out.append({"kind": m.group(1).lower(), "text": m.group(2)})
    return out


class TranscriptStore:
    """The full-context store: the raw dialogue, rendered verbatim (duet `full`)."""

    def __init__(self):
        self.turns = []            # (speaker, text)

    def add(self, speaker, text):
        self.turns.append((speaker, text))

    def render(self, title):
        if not self.turns:
            return ""
        lines = [title]
        for speaker, text in self.turns:
            lines.append(f"{speaker}: {text}")
        return "\n\n".join([lines[0]] + lines[1:])

    def as_json(self):
        return json.dumps({"turns": [{"speaker": s, "text": t} for s, t in self.turns]},
                          indent=2)
