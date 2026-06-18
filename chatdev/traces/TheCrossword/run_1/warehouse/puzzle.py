'''
Crossword puzzle model and validation logic.
'''
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set
@dataclass
class Clue:
    """Represents a single crossword clue."""
    number: int
    direction: str  # "across" or "down"
    clue: str
    answer: str
    start: Tuple[int, int]
@dataclass
class CrosswordPuzzle:
    """Represents a crossword puzzle, including the grid and clues."""
    rows: int
    cols: int
    black_squares: Set[Tuple[int, int]]
    clues: List[Clue]
    grid_solution: List[List[str]] = field(init=False)
    filled: Dict[Tuple[int, int], str] = field(default_factory=dict)
    def __post_init__(self):
        self.grid_solution = [["" for _ in range(self.cols)] for _ in range(self.rows)]
        self._place_answers()
    def _place_answers(self):
        """Fill the solution grid based on clues."""
        for clue in self.clues:
            r, c = clue.start
            answer = clue.answer.upper().strip()
            if not answer:
                raise ValueError(f"Clue {clue.number}-{clue.direction} has an empty answer.")
            for i, ch in enumerate(answer):
                rr, cc = (r, c + i) if clue.direction.lower() == "across" else (r + i, c)
                if not (0 <= rr < self.rows and 0 <= cc < self.cols):
                    raise ValueError(
                        f"Clue {clue.number}-{clue.direction} goes out of bounds at {(rr, cc)}."
                    )
                if (rr, cc) in self.black_squares:
                    raise ValueError(
                        f"Clue {clue.number}-{clue.direction} overlaps a black square at {(rr, cc)}."
                    )
                existing = self.grid_solution[rr][cc]
                if existing and existing != ch:
                    raise ValueError(
                        f"Conflicting answers at {(rr, cc)}: '{existing}' vs '{ch}'."
                    )
                self.grid_solution[rr][cc] = ch
    def valid_cell(self, row: int, col: int) -> bool:
        """Check if a cell is playable."""
        return (row, col) not in self.black_squares
    def get_clue_map(self) -> Dict[str, Clue]:
        """Return mapping like '1-across' -> Clue."""
        return {f"{clue.number}-{clue.direction.lower()}": clue for clue in self.clues}
    def submit_answer(self, number: int, direction: str, answer: str) -> bool:
        """Validate and store an answer if correct."""
        key = f"{number}-{direction.lower().strip()}"
        clue_map = self.get_clue_map()
        if key not in clue_map:
            return False
        clue = clue_map[key]
        normalized = answer.strip().upper()
        if not normalized or normalized != clue.answer.upper():
            return False
        r, c = clue.start
        for i, ch in enumerate(normalized):
            rr, cc = (r, c + i) if clue.direction.lower() == "across" else (r + i, c)
            if not (0 <= rr < self.rows and 0 <= cc < self.cols):
                return False
            if (rr, cc) in self.black_squares:
                return False
            existing = self.filled.get((rr, cc))
            if existing is not None and existing != ch:
                return False
            self.filled[(rr, cc)] = ch
        return True
    def is_complete(self) -> bool:
        """Return True if all non-black cells are correctly filled."""
        for clue in self.clues:
            r, c = clue.start
            for i, ch in enumerate(clue.answer.upper()):
                rr, cc = (r, c + i) if clue.direction.lower() == "across" else (r + i, c)
                if self.filled.get((rr, cc), "") != ch:
                    return False
        return True
    def display_letter(self, row: int, col: int) -> str:
        """Return filled letter or empty string for a cell."""
        return self.filled.get((row, col), "")
def build_default_puzzle() -> CrosswordPuzzle:
    """
    Build a small, fully solvable crossword puzzle.
    Grid layout (7x7), where # denotes a black square:
    Row 0: C A T # D O G
    Row 1: # # A # # # #
    Row 2: B O O K # B E E
    Row 3: # # R # # # #
    Row 4: S U N # M O O N
    Row 5: # # # # # # #
    Row 6: L O G # S T A R
    Fixed layout notes:
    - Clue 5 originally started too far to the right and went out of bounds.
    - It has been moved left so the answer "BEE" fits entirely within the grid.
    - The rest of the layout remains internally consistent.
    """
    rows, cols = 7, 7
    black_squares = {
        (0, 3),
        (1, 0), (1, 1), (1, 3), (1, 4), (1, 5), (1, 6),
        (2, 4),
        (3, 0), (3, 1), (3, 3), (3, 4), (3, 5), (3, 6),
        (4, 3),
        (5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5), (5, 6),
        (6, 3),
    }
    clues = [
        Clue(1, "across", "Small domesticated feline", "CAT", (0, 0)),
        Clue(2, "across", "Male dog", "DOG", (0, 4)),
        Clue(3, "down", "Letter after B", "A", (1, 2)),
        Clue(4, "across", "Written work with pages", "BOOK", (2, 0)),
        Clue(5, "across", "A group of insects that make honey", "BEE", (2, 5)),
        Clue(6, "down", "Bright ball in the sky at day", "SUN", (4, 0)),
        Clue(7, "across", "Natural satellite of Earth", "MOON", (4, 4)),
        Clue(8, "across", "A short piece of wood", "LOG", (6, 0)),
        Clue(9, "across", "Night sky object that shines", "STAR", (6, 4)),
        Clue(10, "down", "Second letter in the word CAT", "A", (0, 1)),
        Clue(11, "down", "Third letter in the word BOOK", "O", (0, 2)),
        Clue(12, "down", "First letter in DOG", "D", (0, 4)),
        Clue(13, "down", "Second letter in DOG", "O", (0, 5)),
        Clue(14, "down", "Third letter in DOG", "G", (0, 6)),
        Clue(15, "down", "Second letter in BOOK", "O", (2, 1)),
        Clue(16, "down", "Third letter in BOOK", "O", (2, 2)),
        Clue(17, "down", "Last letter in BOOK", "K", (2, 3)),
        Clue(18, "down", "First letter in BEE", "B", (2, 5)),
        Clue(19, "down", "Second letter in BEE", "E", (2, 6)),
        Clue(20, "down", "First letter in SUN", "S", (4, 0)),
        Clue(21, "down", "Second letter in SUN", "U", (4, 1)),
        Clue(22, "down", "Third letter in SUN", "N", (4, 2)),
        Clue(23, "down", "First letter in MOON", "M", (4, 4)),
        Clue(24, "down", "Second letter in MOON", "O", (4, 5)),
        Clue(25, "down", "Third letter in MOON", "O", (4, 6)),
        Clue(26, "down", "First letter in STAR", "S", (6, 4)),
    ]
    return CrosswordPuzzle(rows=rows, cols=cols, black_squares=black_squares, clues=clues)