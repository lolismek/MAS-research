"""Central config for the MAF-Magentic vs. MAST-GAIA evaluation.

All model access goes through the Perplexity Agent API (the user provides a
PERPLEXITY_API_KEY). Note: Perplexity uses PROVIDER-PREFIXED model ids and the
Agent API endpoint is https://api.perplexity.ai/v1/agent . Whether this is
drop-in OpenAI chat-completions compatible is UNVERIFIED -> confirm before the
MAS run (see run_mas.py TODO).
"""
import os
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent.parent          # MAS-memory-research/


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from .env.local / .env (gitignored) into os.environ.

    Lets the user hand off the Perplexity key via a file instead of pasting the
    secret into chat. Existing env vars take precedence (don't clobber).
    """
    for fname in (".env.local", ".env"):
        f = ROOT / fname
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)


_load_dotenv()
MAST = ROOT / "MAST"
GAIA_ROOT = MAST / "traces" / "MagenticOne_GAIA"
GAIA_LEVEL_DIRS = {
    1: GAIA_ROOT / "gaia_validation_level_1__MagenticOne",
    2: GAIA_ROOT / "gaia_validation_level_2__MagenticOne",
    3: GAIA_ROOT / "gaia_validation_level_3__MagenticOne",
}
DEFINITIONS_TXT = MAST / "taxonomy_definitions_examples" / "definitions.txt"
EXAMPLES_TXT = MAST / "taxonomy_definitions_examples" / "examples.txt"
CAT2_JSONL = ROOT / "cat2_extraction" / "cat2_failures.jsonl"

RESULTS = ROOT / "results"
TASKS_JSONL = RESULTS / "tasks.jsonl"
RUNS_DIR = RESULTS / "runs"
JUDGED_DIR = RESULTS / "judged"
SUMMARY_JSON = RESULTS / "summary.json"
SUMMARY_MD = RESULTS / "summary.md"

# ---------------------------------------------------------------- API
PPLX_API_KEY_ENV = "PERPLEXITY_API_KEY"
PPLX_BASE_URL = "https://api.perplexity.ai"          # Sonar/chat-completions base
PPLX_AGENT_ENDPOINT = "https://api.perplexity.ai/v1/agent"   # frontier-model proxy

def api_key() -> str:
    k = os.environ.get(PPLX_API_KEY_ENV)
    if not k:
        raise RuntimeError(f"Set {PPLX_API_KEY_ENV} in the environment.")
    return k

# ---------------------------------------------------------------- models
# MAS arm (confirmed available on Perplexity Agent API):
MAS_MODEL = "openai/gpt-5.4-mini"
# Judge: pure gpt-5.4 (stronger than the MAS model -> avoids same-model self-judging,
# more trustworthy labels). Verified on Perplexity at $2.50/$15.00 per 1M (in/out).
JUDGE_MODEL = "openai/gpt-5.4"
JUDGE_TEMPERATURE = 0.0              # deviates from paper's 1.0 for label determinism

# Approx per-1M-token prices (USD, in/out). Perplexity = first-party, no markup;
# CONFIRM exact numbers against docs.perplexity.ai pricing before trusting $ report.
PRICES = {
    "openai/gpt-5.4-mini": (0.75, 4.50),
    "openai/gpt-5.4-nano": (0.20, 1.20),   # approx
    "openai/gpt-5-mini":   (0.40, 2.00),   # approx
    "openai/gpt-5.4":      (2.50, 15.0),
    "anthropic/claude-haiku-4-5":  (1.00, 5.00),   # approx
    "anthropic/claude-sonnet-4-6": (3.00, 15.0),   # approx
    "anthropic/claude-opus-4-8":   (15.0, 75.0),   # approx
}
JUDGE_CANDIDATES = [
    "openai/gpt-5.4-nano", "openai/gpt-5-mini", "anthropic/claude-haiku-4-5",  # cheap
    "openai/gpt-5.4", "anthropic/claude-sonnet-4-6",                            # strong
]

# ---------------------------------------------------------------- experiment
N_TASKS = 15
RUNS_PER_TASK = 3
LEVEL_MIX = {1: 6, 2: 6, 3: 3}        # ~all levels, L3 underweighted
MAX_L3 = 3

# MAF-Magentic inner-loop limits (cost / runaway control)
MAX_ROUND_COUNT = 10
MAX_STALL_COUNT = 3
MAX_RESET_COUNT = 2

# The 14 MAST failure modes, in fixed order.
MODES = ["1.1", "1.2", "1.3", "1.4", "1.5",
         "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
         "3.1", "3.2", "3.3"]
CAT2 = ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"]
