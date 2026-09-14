"""Two-step tool roundtrip on Tinker with our own XML convention (no native `tools`)."""
import json, sys
sys.path.insert(0, "lip/harness")
from llm import TinkerChat, tools_to_prompt, spend
tools = [{"name": "search", "description": "Search the offline Wikipedia corpus. Returns top-5 titles with snippets.",
          "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "search query"}}}},
         {"name": "open", "description": "Open a page by exact title; returns one chunk.",
          "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "page": {"type": "integer", "description": "chunk number, default 1"}}}},
         {"name": "finish", "description": "Submit the final answer.",
          "parameters": {"type": "object", "properties": {"answer": {"type": "string"}}}}]
sysmsg = "You answer questions using only the tools. Call exactly one tool per turn. Never answer from memory.\n\n" + tools_to_prompt(tools)
c = TinkerChat()
msgs = [{"role": "system", "content": sysmsg},
        {"role": "user", "content": "Question: Who was the guitar player for the Dugites from 1982-1983?"}]
r = c.chat(msgs, tag="probe")
print("STEP1 calls:", r["tool_calls"], "| text:", repr(r["content"][:100]), "| finish:", r["finish"], "| reasoning chars:", len(r["reasoning"]))
msgs.append({"role": "assistant", "content": r["raw_content"]})
msgs.append({"role": "user", "content": "<tool_response>\n1. The Dugites — Australian new wave band formed in Perth in 1978. Members included Lynda Nutter, Peter Crosbie, Gunther Berghofer, Clarence Bailey, Paul Noonan, Andrew Pendlebury (guitar, 1982-1983).\n2. Andrew Pendlebury — Australian guitarist-songwriter.\n</tool_response>"})
r = c.chat(msgs, tag="probe")
print("STEP2 calls:", r["tool_calls"], "| text:", repr(r["content"][:200]), "| finish:", r["finish"])
print("spend so far $%.4f" % spend())
