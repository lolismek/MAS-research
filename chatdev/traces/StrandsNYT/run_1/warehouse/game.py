"""
Game logic for the Strands-like puzzle.
"""
from collections import defaultdict
from puzzles import PUZZLES
from utils import are_adjacent, board_contains_path, normalize_word
def touches_opposite_sides(path, rows: int, cols: int) -> bool:
    """Return True if a path touches two opposite sides of the board."""
    touches_top = any(r == 0 for r, c in path)
    touches_bottom = any(r == rows - 1 for r, c in path)
    touches_left = any(c == 0 for r, c in path)
    touches_right = any(c == cols - 1 for r, c in path)
    return (touches_top and touches_bottom) or (touches_left and touches_right)
class StrandsGame:
    """Manage puzzle state, word finding, hints, and completion."""
    def __init__(self) -> None:
        self.puzzle_name = next(iter(PUZZLES.keys()))
        self.load_puzzle(self.puzzle_name)
    def load_puzzle(self, puzzle_name: str) -> None:
        """Load a puzzle by name and validate it strictly."""
        if puzzle_name not in PUZZLES:
            raise KeyError(f"Unknown puzzle: {puzzle_name}")
        puzzle = PUZZLES[puzzle_name]
        self._validate_puzzle(puzzle)
        self.puzzle_name = puzzle_name
        self.theme = puzzle["theme"]
        self.board = [row[:] for row in puzzle["board"]]
        self.rows = len(self.board)
        self.cols = len(self.board[0])
        self.theme_words = [normalize_word(w) for w in puzzle["theme_words"]]
        self.spangram = normalize_word(puzzle["spangram"])
        self.spangram_path = list(puzzle["spangram_path"])
        self.word_paths = {normalize_word(k): list(v) for k, v in puzzle["word_paths"].items()}
        self.all_paths = dict(self.word_paths)
        self.all_paths[self.spangram] = self.spangram_path
        self.found_theme_words = set()
        self.found_theme_cells = set()
        self.spangram_cells = set()
        self.filled_cells = set()
        self.non_theme_words = []
        self._non_theme_word_counts = defaultdict(int)
        self._history = []
        self._hint_pool = list(puzzle.get("hints", []))
    def _validate_puzzle(self, puzzle: dict) -> None:
        """Validate dimensions, paths, spelling, coverage, and spangram rules."""
        board = puzzle["board"]
        if len(board) != 6:
            raise ValueError("Puzzle board must have exactly 6 rows.")
        if any(len(row) != 8 for row in board):
            raise ValueError("Puzzle board must have exactly 8 columns in every row.")
        spangram = normalize_word(puzzle["spangram"])
        word_paths = {normalize_word(k): v for k, v in puzzle["word_paths"].items()}
        word_paths[spangram] = puzzle["spangram_path"]
        covered = set()
        for word, path in word_paths.items():
            if not board_contains_path(board, path):
                raise ValueError(f"Invalid path for word: {word}")
            spelled = "".join(board[r][c] for r, c in path)
            if normalize_word(spelled) != word:
                raise ValueError(f"Path for word '{word}' does not spell the word.")
            for cell in path:
                if cell in covered:
                    raise ValueError("Theme paths must not overlap.")
                covered.add(cell)
        if not touches_opposite_sides(puzzle["spangram_path"], 6, 8):
            raise ValueError("Spangram must touch two opposite sides of the board.")
        if len(covered) != 6 * 8:
            raise ValueError("All board cells must be covered exactly once by solution paths.")
    def reset(self) -> None:
        """Reset state while keeping the same puzzle."""
        self.load_puzzle(self.puzzle_name)
    def is_adjacent(self, a, b) -> bool:
        """Check if two cells are adjacent."""
        return are_adjacent(a, b)
    def word_from_path(self, path) -> str:
        """Build a word from a sequence of cells."""
        return "".join(self.board[r][c] for r, c in path)
    def submit_attempt(self, word: str, path):
        """
        Submit a path attempt.
        Returns dict with keys:
        - found: bool
        - reason: str
        """
        normalized = normalize_word(word)
        if not path or not board_contains_path(self.board, path):
            return {"found": False, "reason": "invalid"}
        canonical_path = self.word_paths.get(normalized)
        if normalized == self.spangram:
            canonical_path = self.spangram_path
        if canonical_path is None or list(path) != list(canonical_path):
            return {"found": False, "reason": "invalid"}
        if normalized == self.spangram:
            if normalized in self.found_theme_words:
                return {"found": False, "reason": "duplicate"}
            self.found_theme_words.add(normalized)
            self.spangram_cells.update(path)
            self.found_theme_cells.update(path)
            self.filled_cells.update(path)
            self._history.append(("theme", normalized, list(path)))
            return {"found": True, "reason": "spangram"}
        if normalized in self.theme_words:
            if normalized in self.found_theme_words:
                return {"found": False, "reason": "duplicate"}
            self.found_theme_words.add(normalized)
            self.found_theme_cells.update(path)
            self.filled_cells.update(path)
            self._history.append(("theme", normalized, list(path)))
            return {"found": True, "reason": "theme"}
        return {"found": False, "reason": "non-theme"}
    def record_non_theme_word(self, word: str) -> None:
        """Record a non-theme word and award hints every 3 unique non-theme words."""
        normalized = normalize_word(word)
        if not normalized:
            return
        self._non_theme_word_counts[normalized] += 1
        if normalized not in self.non_theme_words:
            self.non_theme_words.append(normalized)
    def hints_available(self) -> int:
        """Return how many hints are currently available."""
        return len(self.non_theme_words) // 3
    def get_hint(self):
        """Return a hint if available."""
        if self.hints_available() <= 0 or not self._hint_pool:
            return None
        index = len(self.non_theme_words) // 3 - 1
        if index < 0:
            return None
        if index >= len(self._hint_pool):
            index = len(self._hint_pool) - 1
        return self._hint_pool[index]
    def undo_last_word(self) -> bool:
        """Undo the last found theme/spangram word."""
        if not self._history:
            return False
        kind, word, path = self._history.pop()
        if word in self.found_theme_words:
            self.found_theme_words.remove(word)
        self._recompute_filled_cells()
        return True
    def _recompute_filled_cells(self) -> None:
        """Recompute highlighted cells based on current found words."""
        self.found_theme_cells.clear()
        self.spangram_cells.clear()
        self.filled_cells.clear()
        for kind, word, path in self._history:
            if word in self.found_theme_words:
                self.found_theme_cells.update(path)
                self.filled_cells.update(path)
                if word == self.spangram:
                    self.spangram_cells.update(path)
    def is_complete(self) -> bool:
        """Check whether all theme words and spangram were found and the board is filled."""
        return (
            self.theme_words_found_complete()
            and self.spangram in self.found_theme_words
            and len(self.filled_cells) == self.rows * self.cols
        )
    def theme_words_found_complete(self) -> bool:
        """Check whether all non-spangram theme words were found."""
        return all(w in self.found_theme_words for w in self.theme_words)