"""Probe Tinker: tool-call format, think format, usage. Reads .env at repo root."""
import json, os, sys, time
from dotenv import load_dotenv; load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
from openai import OpenAI
c = OpenAI(api_key=os.environ["TINKER_API_KEY"],
           base_url="https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1")
MODEL = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen3.6-35B-A3B"
tools = [{"type": "function", "function": {"name": "search", "description": "Search Wikipedia.",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}]
t = time.time()
r = c.chat.completions.create(model=MODEL, max_tokens=2000, tools=tools,
    messages=[{"role": "system", "content": "You answer questions using the search tool. Always search before answering."},
              {"role": "user", "content": "Who was the guitar player for the Dugites from 1982-1983?"}])
m = r.choices[0].message
print("latency", round(time.time() - t, 1), "finish", r.choices[0].finish_reason)
print("usage", r.usage.model_dump() if r.usage else None)
print("tool_calls", [tc.model_dump() for tc in (m.tool_calls or [])])
print("reasoning_content", repr((getattr(m, "reasoning_content", None) or "")[:300]))
print("content", repr((m.content or "")[:600]))
extra = getattr(m, "model_extra", None)
print("extra keys", list(extra.keys()) if extra else None)
