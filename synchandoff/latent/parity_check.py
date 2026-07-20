"""HF-vs-vLLM text parity check (LITREVIEW global implementation note).

Run ON tigerfish (both endpoints local):
  /tmp/aij2115/latentenv/bin/python parity_check.py

Sends the same messages(+tools) greedy to
  - vLLM      http://localhost:8801/v1/chat/completions (text-arm backend)
  - latent    http://localhost:8802/v1/chat/completions (no artifact)
and reports prefix agreement. Exact token equality is NOT expected (different
AWQ kernels: vLLM Marlin vs our pure-torch dequant; different attention
kernels) — the pass bar is same-content, same-format behavior: long common
prefix and/or equivalent final answer + tool-call syntax.
"""
import json
import os

import requests

VLLM = os.environ.get("PARITY_VLLM",
                      "http://localhost:8804") + "/v1/chat/completions"
LAT = os.environ.get("PARITY_LAT",
                     "http://localhost:8802") + "/v1/chat/completions"
MODEL = os.environ.get("PARITY_MODEL", "Qwen/Qwen3-8B")

TOOLS = [{"type": "function", "function": {
    "name": "bash",
    "description": "Run a shell command in the repository container (cwd /workspace/test_repo).",
    "parameters": {"type": "object", "properties": {
        "command": {"type": "string", "description": "The shell command to run."}},
        "required": ["command"]}}}]

CASES = [
    ("plain", [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "In one sentence, what does the pytest -k flag do?"}],
     None),
    ("tools", [
        {"role": "system", "content": "You are a software engineer in a Python repo. "
         "Use the bash tool to investigate. The tests in tests/test_x.py fail."},
        {"role": "user", "content": "Find out which tests fail. Start by listing the tests directory."}],
     TOOLS),
]


def call(url, messages, tools, max_tokens=600):
    body = {"model": MODEL, "messages": messages,
            "temperature": 0.0, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
    r = requests.post(url, json=body, timeout=1800)
    r.raise_for_status()
    d = r.json()["choices"][0]
    msg = d["message"]
    text = msg.get("content") or ""
    if msg.get("tool_calls"):
        text += "".join(f"\n<TOOLCALL {t['function']['name']} "
                        f"{t['function']['arguments']}>" for t in msg["tool_calls"])
    return text, d.get("finish_reason")


def common_prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def main():
    for name, messages, tools in CASES:
        va, vf = call(VLLM, messages, tools)
        la, lf = call(LAT, messages, tools)
        cp = common_prefix_len(va, la)
        print(f"=== case {name}: vllm {len(va)} chars ({vf}), "
              f"latent {len(la)} chars ({lf}), common prefix {cp} chars")
        print("--- vllm head ---")
        print(va[:500])
        print("--- latent head ---")
        print(la[:500])
        print(json.dumps({"case": name, "prefix": cp,
                          "vllm_len": len(va), "lat_len": len(la)}))


if __name__ == "__main__":
    main()
