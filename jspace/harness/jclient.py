"""Client for the J-space extraction service (extractor/server.py).

One call per hand-off edge in the note_jspace arm: A's stored transcript (plus the
tool schemas it was served with, so the realized prompt matches) goes over, the
compressed workspace-readout blurb comes back. Failures never kill a run — the
successor just gets the plain note and the error is recorded in the trace."""
import os

import requests

JSPACE_URL = os.environ.get("JSPACE_URL", "http://127.0.0.1:8398")
TIMEOUT = int(os.environ.get("JSPACE_TIMEOUT", "300"))


def extract(transcript_messages, tools=None):
    """-> (blurb:str|None, meta:dict). meta['error'] set on failure."""
    msgs = [{k: v for k, v in m.items() if k != "reasoning_content"}
            for m in transcript_messages]
    try:
        r = requests.post(f"{JSPACE_URL}/extract",
                          json={"messages": msgs, "tools": tools}, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        if "error" in d:
            return None, {"error": d["error"]}
        return d["blurb"], d.get("meta", {})
    except Exception as e:
        return None, {"error": f"{type(e).__name__}: {e}"}
