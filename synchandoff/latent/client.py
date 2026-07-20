"""HTTP client for the latent server (tigerfish :8802, reached from piranha
through the ssh tunnel — see infra/README.md). Used by handoff/latent_arms.py
(artifact building) and latent/probe/ (activation capture)."""
import os

import requests

BASE = os.environ.get("SYNCHANDOFF_LATENT_BASE", "http://localhost:8802")
TIMEOUT = 3600


def _post(path, body):
    r = requests.post(f"{BASE}{path}", json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def health():
    return requests.get(f"{BASE}/health", timeout=30).json()


def prefill_capture(messages=None, raw_text=None, tools=None,
                    add_generation_prompt=False, capture_layers=None,
                    return_hidden=None, session_id=None):
    body = {"add_generation_prompt": add_generation_prompt}
    if messages is not None:
        body["messages"] = messages
    if raw_text is not None:
        body["raw_text"] = raw_text
    if tools:
        body["tools"] = tools
    if capture_layers:
        body["capture_layers"] = capture_layers
    if return_hidden:
        body["return_hidden"] = return_hidden
    if session_id:
        body["session_id"] = session_id
    return _post("/prefill_capture", body)


def make_artifact(arm, session_id=None, params=None, artifact_id=None):
    return _post("/make_artifact", {"arm": arm, "session_id": session_id,
                                    "params": params or {},
                                    "artifact_id": artifact_id})


def session_free(session_id):
    return _post("/session_free", {"session_id": session_id})


def generate(messages, tools=None, max_tokens=2048, temperature=0.0,
             latent_artifact_id=None):
    body = {"messages": messages, "max_tokens": max_tokens,
            "temperature": temperature}
    if tools:
        body["tools"] = tools
    if latent_artifact_id:
        body["latent_artifact_id"] = latent_artifact_id
    return _post("/v1/chat/completions", body)
