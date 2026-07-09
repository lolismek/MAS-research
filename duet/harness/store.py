"""The one SharedStore per run: the belief ledger (board/extract arms) and the raw
transcript store (full arm), plus their renders under the rendering contract
(PLAN "The seam"; hygiene rule 4 — attributed entries, per-agent structure never
blended; the preamble lives in prompts.STORE_PREAMBLE and is applied by the arm).

The ledger is the study's manipulated representation: entries
    {id, author, object, belief, confidence, status}
with revision (status active -> revised/retracted, history kept) — persistence +
revision + lateral visibility are the variables `board` manipulates vs `sop`'s
publish-once typed payload (PLAN "Axis hygiene").
"""
import re


class BeliefLedger:
    """Append-and-revise belief store. Entries are never deleted: a revision points at
    its predecessor (`revises`), a retraction flips status — so the ledger's history is
    itself auditable (who believed what, when, and what changed)."""

    def __init__(self):
        self.entries = []                     # dicts, id = b1, b2, ... in insert order

    def add(self, author, obj, belief, confidence, kind="belief"):
        """`kind`: 'belief' (a subjective stance — the default; all agent-written board
        entries) or 'observation' (a concrete found fact — set by the `extract` observer,
        which types objective objects as memory vs subjective ones as belief)."""
        e = dict(id=f"b{len(self.entries) + 1}", author=author, object=(obj or "").strip(),
                 belief=(belief or "").strip(), confidence=_clamp(confidence),
                 kind=("observation" if kind == "observation" else "belief"),
                 status="active", revises=None)
        self.entries.append(e)
        return e

    def revise(self, author, belief_id, belief=None, confidence=None, status=None):
        """Revise/retract by id. The old entry is marked superseded; a non-retraction
        writes a fresh active entry so authorship of the correction is attributed."""
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
        """The ledger as the shared-state block body: every ACTIVE belief attributed
        [id · author], plus one line per superseded entry so corrections are visible
        (a successor should see that a belief WAS revised, not just its final form)."""
        if not self.entries:
            return ""
        lines = []
        for e in self.entries:
            head = f"[{e['id']} · {e['author']}]"
            if e["status"] == "active":
                rev = f" (revises {e['revises']})" if e["revises"] else ""
                # objective objects are surfaced as observed memory, subjective ones as
                # belief (the `extract` typing; plain agent-written entries stay belief)
                lead = "observed — " if e.get("kind") == "observation" else ""
                lines.append(f"{head} {lead}{e['object']}: {e['belief']} "
                             f"(confidence {e['confidence']:.2f}){rev}")
            elif e["status"] == "retracted":
                lines.append(f"{head} {e['object']}: RETRACTED by {e.get('retracted_by', '?')} "
                             f"— was: {e['belief']}")
            else:                              # revised: point forward, keep it one line
                lines.append(f"{head} {e['object']}: superseded — was: {e['belief']}")
        return "Beliefs recorded so far (id · author):\n" + "\n".join(lines)

    def to_json(self):
        return list(self.entries)


def _clamp(c):
    try:
        return max(0.0, min(1.0, float(c)))
    except (TypeError, ValueError):
        return 0.5


# --- observer-line parsing (`extract` arm) -------------------------------------
# The observer types each line OBSERVATION: (objective/memory) or BELIEF: (subjective).
_BELIEF_LINE = re.compile(r"^\s*(OBSERVATION|BELIEF)\s*:\s*(.+?)\s*$", re.M | re.I)


def parse_belief_lines(text):
    """OBSERVER_SYS output -> [(kind, object, belief, confidence)]. Lines are
    '<OBSERVATION|BELIEF>: <object> | <claim> | <confidence>'; a lone 'BELIEF: none'
    yields []. `kind` is 'observation' or 'belief' (defaulting to belief)."""
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


# --- raw-transcript store (`full` arm) ------------------------------------------
TRANSCRIPT_TOOL_CHARS = 700      # per tool result inside a render (raw access, bounded
TRANSCRIPT_TOTAL_CHARS = 12000   # by the context wall — flooding is the finding, not a crash)


THINK_CHARS = 2000               # per recovered <think> trace inside an observer render


def render_transcript(result, tool_chars=TRANSCRIPT_TOOL_CHARS,
                      total_chars=TRANSCRIPT_TOTAL_CHARS, include_reasoning=False):
    """A producer's raw working log as one attributed text block: assistant text, tool
    calls with args, tool observations (each clipped). Recovered <think> is included
    only when `include_reasoning` (the `extract` observer reads the full trace incl.
    reasoning; `full` is raw ACCESS to what a log viewer shows, so it excludes it).
    Clipping keeps newest content: the block is truncated from the FRONT if over
    budget (the latest evidence is what a merge needs most)."""
    lines = []
    for m in result.transcript:
        role = m.get("role")
        if role == "assistant":
            if include_reasoning and m.get("reasoning_content"):
                r = m["reasoning_content"].strip()
                if len(r) > THINK_CHARS:
                    r = r[:THINK_CHARS] + f" …[+{len(r) - THINK_CHARS} chars]"
                lines.append(f"{result.role} (thinking): {r}")
            if m.get("content"):
                lines.append(f"{result.role}: {m['content'].strip()}")
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                lines.append(f"{result.role} -> {fn.get('name')}({(fn.get('arguments') or '')[:200]})")
        elif role == "tool":
            c = (m.get("content") or "").strip()
            if len(c) > tool_chars:
                c = c[:tool_chars] + f" …[+{len(c) - tool_chars} chars]"
            lines.append(f"  observation: {c}")
        elif role == "user":
            # the producer's own layer-2/3 context is not its work product; skip
            continue
    body = "\n".join(lines)
    if len(body) > total_chars:
        body = f"[…log start elided, {len(body) - total_chars} chars]\n" + body[-total_chars:]
    return body


class TranscriptStore:
    """The `full` arm's store: producers' raw logs in arrival order, rendered as
    per-agent blocks (never blended — rule 4)."""

    def __init__(self):
        self.blocks = []                       # (agent, rendered_log)

    def add(self, result):
        self.blocks.append((result.role, render_transcript(result)))

    def render(self):
        if not self.blocks:
            return ""
        import prompts
        parts = [prompts.FULL_TRANSCRIPT_HEADER.format(agent=agent) + "\n" + body
                 for agent, body in self.blocks]
        return "\n\n".join(parts)
