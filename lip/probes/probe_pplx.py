"""Probe Perplexity: which model ids resolve on /v1/responses, and what usage/cost looks like."""
import json, os, sys, time, requests
from dotenv import load_dotenv; load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
KEY = os.environ["PERPLEXITY_API_KEY"]
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
models = sys.argv[1:] or ["openai/gpt-5.4-mini", "openai/gpt-5.4", "openai/gpt-5.5", "openai/gpt-5.5-mini",
                          "openai/o3", "anthropic/claude-sonnet-4.5", "google/gemini-2.5-pro", "sonar-pro", "sonar-reasoning-pro"]
for m in models:
    body = {"model": m, "input": "Reply with the single word: ready.", "max_output_tokens": 50}
    t = time.time()
    r = requests.post("https://api.perplexity.ai/v1/responses", headers=H, json=body, timeout=60)
    dt = round(time.time() - t, 1)
    if r.status_code != 200:
        print(f"{m:32s} HTTP {r.status_code} {r.text[:120]!r}"); continue
    j = r.json()
    txt = "".join(c.get("text", "") for it in j.get("output", []) for c in it.get("content", []) if isinstance(c, dict))
    print(f"{m:32s} OK {dt}s model={j.get('model')} usage={j.get('usage')} text={txt[:40]!r}")
