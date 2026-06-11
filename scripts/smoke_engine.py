"""Engine smoke test: one real generation that should produce a parseable tool call.

Run on a machine with the model available (bren GPU for hf; any machine with
the API key for api). Examples:

    # HF backend (GPU box; ~16GB VRAM for Qwen3-8B, use Qwen/Qwen3-4B on MPS)
    python scripts/smoke_engine.py --backend hf --model Qwen/Qwen3-8B

    # API backend (key from .env PERPLEXITY_API_KEY or env)
    python scripts/smoke_engine.py --backend api --model gpt-5.4-mini \
        --base-url https://api.perplexity.ai --api-key-env PERPLEXITY_API_KEY

Pass criteria: finish_reason == tool_calls, exactly one read_file call with
path == "initial_program.py", no parse errors.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from minicoral.engine import APIEngine, GenRequest, HFEngine

SMOKE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "file path"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the working directory.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

SMOKE_MESSAGES = [
    {"role": "system", "content": "You are a coding agent. Use the provided tools."},
    {"role": "user", "content": "Read the file initial_program.py using the read_file tool."},
]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["hf", "api"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--thinking", action="store_true")
    ns = ap.parse_args()

    if ns.backend == "hf":
        engine = HFEngine(model_name=ns.model, device=ns.device)
    else:
        engine = APIEngine(model_name=ns.model, base_url=ns.base_url,
                           api_key_env=ns.api_key_env)

    req = GenRequest(
        messages=SMOKE_MESSAGES,
        tools=SMOKE_TOOLS,
        max_new_tokens=512,
        temperature=0.7,
        enable_thinking=ns.thinking,
    )
    res = await engine.generate(req)

    print(f"finish_reason:     {res.finish_reason}")
    print(f"text:              {res.text[:200]!r}")
    print(f"thinking:          {res.thinking[:200]!r}")
    print(f"tool_calls:        {[(c.name, c.arguments) for c in res.tool_calls]}")
    print(f"parse_errors:      {[e.error for e in res.parse_errors]}")
    print(f"tokens:            prompt={res.prompt_tokens} completion={res.completion_tokens}")

    ok = (
        len(res.tool_calls) == 1
        and res.tool_calls[0].name == "read_file"
        and res.tool_calls[0].arguments.get("path") == "initial_program.py"
        and not res.parse_errors
    )
    print(f"\nSMOKE {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
