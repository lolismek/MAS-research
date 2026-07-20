"""LLM access: OpenAI chat.completions against the shared Tinker proxy.

The proxy (shared/proxy/server.py on multi-benchmark-eval, already running on
:8744) aliases any model name to Qwen/Qwen3.6-35B-A3B, converts Qwen's text
tool-call syntax into structured tool_calls, and strips the <think> trace.
So this module speaks plain OpenAI chat.completions and nothing else.

Cost is self-metered (Tinker has no usage API): every call is appended to
SYNCHANDOFF_LLM_LOG (default synchandoff/llm_calls.jsonl) with token usage.
"""
import json
import os
import threading
import time

import requests

BASE = os.environ.get("SYNCHANDOFF_LLM_BASE", "http://localhost:8744/m/v1")
MODEL = "gpt-4o"  # aliased upstream to Qwen/Qwen3.6-35B-A3B
TEMPERATURE = 0.0
# Qwen3.6's think trace counts against max_tokens; small caps truncate real
# answers (duet/camel finding). 28k matches their proven regime.
MAX_OUTPUT_TOKENS = int(os.environ.get("SYNCHANDOFF_MAX_TOKENS", "28000"))
# HF-backed latent arms decode at single-digit tok/s: long calls need a
# larger client timeout than the vLLM default (set in run_phase2_latent.sh).
TIMEOUT = int(os.environ.get("SYNCHANDOFF_LLM_TIMEOUT", "600"))
_HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.environ.get("SYNCHANDOFF_LLM_LOG",
                     os.path.join(os.path.dirname(_HERE), "llm_calls.jsonl"))
_log_lock = threading.Lock()

# The proxy replaces a think-truncated reply with this exact sentinel.
PROXY_TRUNCATION_SENTINEL = (
    "[the model could not finish reasoning within the token budget; no action produced this turn]"
)


class Usage:
    def __init__(self):
        self.prompt = 0
        self.completion = 0
        self.calls = 0

    def add(self, u):
        self.prompt += u.get("prompt_tokens", 0)
        self.completion += u.get("completion_tokens", 0)
        self.calls += 1

    def as_dict(self):
        return {"prompt_tokens": self.prompt, "completion_tokens": self.completion,
                "calls": self.calls}


def chat(messages, tools=None, max_tokens=None, tag="", retries=4):
    """One chat.completions call; returns the assistant message dict (with
    'usage' attached under '_usage'). Raises after exhausting retries."""
    body = {"model": MODEL, "messages": messages, "temperature": TEMPERATURE,
            "max_tokens": max_tokens or MAX_OUTPUT_TOKENS}
    if tools:
        body["tools"] = tools
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.post(f"{BASE}/chat/completions", json=body, timeout=TIMEOUT)
            if r.status_code >= 500 or r.status_code == 429:
                last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                time.sleep(4 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            msg = data["choices"][0]["message"]
            usage = data.get("usage") or {}
            msg["_usage"] = usage
            msg["_finish"] = data["choices"][0].get("finish_reason")
            with _log_lock:
                with open(LOG, "a") as f:
                    f.write(json.dumps({"ts": time.time(), "tag": tag,
                                        "usage": usage, "finish": msg["_finish"]}) + "\n")
            return msg
        except requests.RequestException as e:
            last_err = str(e)[:300]
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {retries} attempts: {last_err}")
