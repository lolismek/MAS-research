import os
from dotenv import load_dotenv
load_dotenv()

# LLM routing now goes through the local proxy via PROXY_URL / MACNET_TAG (see mas/llm.py).
# The legacy OPENAI_API_BASE / OPENAI_API_KEY env vars are no longer required.