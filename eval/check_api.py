"""Connectivity + interface smoke test. Run this FIRST once PERPLEXITY_API_KEY is set.

Confirms the MAS model and judge model are reachable through Perplexity and reports
which interface (Responses vs chat.completions) answered, plus token usage/cost.

Run: PERPLEXITY_API_KEY=... python eval/check_api.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
from llm_client import call_llm

def main():
    for label, model in [("MAS", C.MAS_MODEL), ("JUDGE", C.JUDGE_MODEL)]:
        print(f"\n--- {label}: {model} ---")
        try:
            text, usage = call_llm("Reply with exactly the word: OK", model, temperature=0)
            print("  reply:", (text or "").strip()[:120])
            print("  usage:", usage)
        except Exception as e:
            print("  FAILED:", e)

if __name__ == "__main__":
    main()
