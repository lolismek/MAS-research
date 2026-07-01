# Working-memory (inside-trial) arms — no heavy deps, always available.
from .memory_base import MASMemoryBase   # `empty`   : raw-trajectory working memory
from .chatdev import ChatDevMASMemory    # `chatdev` : periodic LLM-summary working memory

# Cross-trial (long-term) memory arms are OUT OF SCOPE for this project: they back retrieval with a
# Chroma vector store (+ finch / sentence-transformers). We never activate them, so import them
# best-effort and leave them as inert artifacts. If the heavy deps aren't installed the names resolve
# to None; selecting one of these arms then fails loudly (intended — we only run working-memory arms).
try:
    from .generative import GenerativeMASMemory
    from .metagpt import MetaGPTMASMemory
    from .voyager import VoyagerMASMemory
    from .memorybank import MemoryBankMASMemory
    from .GMemory import GMemory
except ImportError as _e:
    import warnings as _warnings
    _warnings.warn(f"cross-trial memory arms not loaded (heavy deps absent): {_e}. "
                   "Working-memory arms (empty/chatdev) are unaffected.")
    GenerativeMASMemory = MetaGPTMASMemory = VoyagerMASMemory = MemoryBankMASMemory = GMemory = None

__all__ = [
    'MASMemoryBase', 
    'ChatDevMASMemory',
    'GenerativeMASMemory',
    'MetaGPTMASMemory',
    'VoyagerMASMemory',
    'MemoryBankMASMemory',
    'GMemory'
]