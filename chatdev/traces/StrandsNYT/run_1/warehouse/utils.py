"""
Utility functions for the Strands-like puzzle game.
"""
def normalize_word(word: str) -> str:
    """Normalize a word for matching."""
    return "".join(ch.lower() for ch in word if ch.isalpha())
def are_adjacent(a, b) -> bool:
    """Return True if two cells are adjacent in any of 8 directions."""
    ar, ac = a
    br, bc = b
    return max(abs(ar - br), abs(ac - bc)) == 1
def board_contains_path(board, path) -> bool:
    """Validate that a path stays inside the board and uses adjacent steps."""
    if not path:
        return False
    rows = len(board)
    cols = len(board[0]) if rows else 0
    seen = set()
    prev = None
    for r, c in path:
        if not (0 <= r < rows and 0 <= c < cols):
            return False
        if (r, c) in seen:
            return False
        seen.add((r, c))
        if prev is not None and not are_adjacent(prev, (r, c)):
            return False
        prev = (r, c)
    return True