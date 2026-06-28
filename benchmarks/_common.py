"""Shared helpers for benchmark prep scripts (stdlib + huggingface_hub only).

Each benchmarks/<name>/prep.py reads a source and writes its sibling tasks.jsonl
in ONE uniform record schema so the MAS harnesses (camel/, autogen_gc/) can load
any benchmark identically:

    {
      "id":            "<bench>_<n>",        # stable, unique
      "bench":         "gaia|gpqa_diamond|math_l5",
      "question":      "<prompt text the agent sees>",
      "expected_answer":"<gold answer>",
      "answer_type":   "freeform|mcq|math",  # drives scoring.match()
      "tool_profile":  "none|math|web|web_compute",
      "meta":          { ...source-specific bookkeeping... }
    }

HF datasets are read with the token in the repo-root .env (HUGGINGFACE_TOKEN);
the token is NEVER written into tasks.jsonl.
"""
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    """Load repo-root .env into os.environ (so HUGGINGFACE_TOKEN is available)."""
    p = os.path.join(REPO_ROOT, ".env")
    if not os.path.exists(p):
        return
    for line in open(p):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def hf_token():
    load_env()
    return os.environ.get("HUGGINGFACE_TOKEN")


def write_tasks(out_path, tasks):
    """Write a list of task dicts as JSONL, sorted-key for stable diffs."""
    with open(out_path, "w") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"wrote {len(tasks)} tasks -> {os.path.relpath(out_path, REPO_ROOT)}")
