#!/usr/bin/env python3
"""
Step-1 backend probe for the multi-benchmark-eval sweep (see PLAN.md).

Goal: de-risk the single biggest unknown BEFORE building any scaffold —
does an open-source model on Tinker's OpenAI-compatible endpoint actually
work, and (critically) does it support TOOL CALLING? AutoGen GroupChat is
tool-driven, and open models behind an OpenAI-compat shim are exactly where
function-calling tends to break.

This deliberately uses NO proxy, NO AutoGen, NO benchmark — just the raw
endpoint, via the same `openai` SDK that AutoGen's OpenAIChatCompletionClient
uses, so an SDK-level incompatibility shows up here.

Runs three checks:
  0. GET /models  -> list available model ids (resolves the EXACT id string).
  1. plain chat/completions -> 200 + token usage present.
  2. chat/completions with a tool schema -> response carries tool_calls.

Cost: a couple of tiny calls, well under the $5 smoke cap.

Prereq (the current blocker): add to eval-clean/.env (or this branch's .env):
    TINKER_API_KEY=sk-...           # required
    # optional overrides:
    # TINKER_BASE_URL=https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1
    # TINKER_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507   # HF org prefix is required

Run (in the conda env that has the `openai` package, e.g. the autogen_gc env):
    python probe_tinker.py
"""
import json
import os
import sys

DEFAULT_BASE = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"
# Base models need the HF org prefix (validated 2026-06-25); the bare name 400s
# with "Tokenizer not supported". /models lists trained checkpoints, not base models.
DEFAULT_MODEL = "Qwen/Qwen3.6-35B-A3B"   # current gen; Qwen3-*-2507 are retired (2026-06-12)


def load_env():
    """Minimal .env loader (mirrors shared/proxy/server.py). Checks this dir,
    then the sibling eval-clean worktree, so the existing keys file is reused."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, ".env"),
        os.path.join(here, "..", "eval-clean", ".env"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()
    key = os.environ.get("TINKER_API_KEY", "")
    base = os.environ.get("TINKER_BASE_URL", DEFAULT_BASE)
    model = os.environ.get("TINKER_MODEL", DEFAULT_MODEL)

    if not key:
        sys.exit(
            "BLOCKED: no TINKER_API_KEY found.\n"
            "Add `TINKER_API_KEY=...` to this branch's .env or eval-clean/.env, "
            "then re-run. (This is the only thing gating step 1.)"
        )

    try:
        from openai import OpenAI
    except ImportError:
        sys.exit(
            "The `openai` package isn't importable here. Run inside the conda env "
            "that has it (the same one eval-clean's autogen harness uses)."
        )

    client = OpenAI(api_key=key, base_url=base)
    print(f"base_url = {base}")
    print(f"model    = {model}\n")

    # --- Check 0: list models (resolves the exact id string Tinker expects) ---
    print("[0] GET /models ...")
    try:
        models = client.models.list()
        ids = [m.id for m in models.data]
        print(f"    OK — {len(ids)} model(s). First ~20:")
        for mid in ids[:20]:
            marker = "  <-- matches TINKER_MODEL" if mid == model else ""
            print(f"      {mid}{marker}")
        print("    (Listed ids are trained sampler-weight checkpoints, not the base-model "
              "catalog — base models are passed by HF name, e.g. Qwen/Qwen3-...)")
    except Exception as e:
        print(f"    /models failed ({type(e).__name__}: {e}). "
              f"Not fatal — some endpoints omit it; continuing.")

    # --- Check 1: plain completion (connectivity + usage) ---
    print("\n[1] plain chat/completions ...")
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: PONG"}],
            max_tokens=16,
            temperature=0,
        )
        text = (r.choices[0].message.content or "").strip()
        usage = r.usage
        print(f"    OK — reply={text!r}")
        if usage:
            print(f"    usage: prompt={usage.prompt_tokens} "
                  f"completion={usage.completion_tokens} total={usage.total_tokens}")
        else:
            print("    WARN: no usage block returned (cost tracking will need a fallback).")
    except Exception as e:
        sys.exit(f"    FAILED ({type(e).__name__}: {e}). "
                 f"Backend isn't usable — stop here and resolve before step 2.")

    # --- Check 2: tool calling (the AutoGen-critical capability) ---
    print("\n[2] chat/completions WITH a tool schema (the make-or-break check) ...")
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "City name"}},
                "required": ["city"],
            },
        },
    }]
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": "Use the get_weather tool to check the weather in Paris."}],
            tools=tools,
            tool_choice="auto",
            max_tokens=128,
            temperature=0,
        )
        msg = r.choices[0].message
        calls = msg.tool_calls or []
        if calls:
            c = calls[0]
            try:
                argstr = c.function.arguments
                args = json.loads(argstr) if argstr else {}
            except Exception:
                args = argstr
            print(f"    OK — tool_calls returned: name={c.function.name!r} args={args}")
            ok = c.function.name == "get_weather" and isinstance(args, dict) and "city" in args
            print("    => TOOL CALLING WORKS." if ok else
                  "    => tool_calls present but malformed — inspect before relying on it.")
        else:
            print(f"    NO tool_calls. content={ (msg.content or '')[:200]!r}")
            print("    => Tool calling did NOT trigger. This is the AutoGen blocker — "
                  "investigate (model id? tool_choice? does this model support tools?) "
                  "before wiring AutoGen in step 2.")
    except Exception as e:
        print(f"    FAILED ({type(e).__name__}: {e}). Tool calling unsupported/incompatible "
              f"on this endpoint — the #1 thing to resolve before step 2.")

    print("\nDone. Green on [1] and [2] => proceed to step 2 "
          "(point the eval-clean harness at Tinker, run 1 GAIA task).")


if __name__ == "__main__":
    main()
