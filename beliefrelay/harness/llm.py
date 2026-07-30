"""Minimal chat client for the shared Tinker proxy (/m/<tag>/v1).

The proxy (multi-benchmark-eval worktree, shared/proxy/server.py) aliases model
'gpt-4o' to Qwen/Qwen3.6-35B-A3B, strips the inline <think>...</think> trace from
`content` (so the relay channel carries only the visible message — the think stays
agent-internal, which is exactly the channel semantics this experiment needs), and
appends every call to calls.jsonl for self-metering.
"""
import os
import time

import requests

PROXY = os.environ.get("PROXY_URL", "http://127.0.0.1:8744")
MODEL = "gpt-4o"  # aliased upstream to Qwen/Qwen3.6-35B-A3B


def chat(tag, messages, max_tokens=16000, temperature=0.7, timeout=1200, retries=4):
    """One chat.completions call. Returns dict(content, usage). Raises after retries."""
    url = f"{PROXY}/m/{tag}/v1/chat/completions"
    body = dict(model=MODEL, messages=messages, max_tokens=max_tokens,
                temperature=temperature)
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(url, json=body, timeout=timeout)
            if r.status_code == 200:
                d = r.json()
                msg = d["choices"][0]["message"]
                return dict(content=(msg.get("content") or "").strip(),
                            usage=d.get("usage") or {},
                            finish=d["choices"][0].get("finish_reason"))
            last = f"HTTP {r.status_code}: {r.text[:300]}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"chat({tag}) failed after {retries} tries: {last}")
