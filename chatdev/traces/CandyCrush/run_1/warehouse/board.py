'''
Board model and match-3 logic.
'''
from __future__ import annotations
import random
from typing import List, Set, Tuple
Candy = int
Position = Tuple[int, int]
class Match3Board:
    """Represents the logical match-3 board and game mechanics."""
    def __init__(self, rows: int = 8, cols: int = 8, candy_types: int = 6) -> None:
        self.rows = rows
        self.cols = cols
        self.candy_types = candy_types
        self.grid: List[List[Candy]] = []
        self.reset()
    def reset(self) -> None:
        """Create a new random board with no initial matches."""
        self.grid = [[self._random_candy() for _ in range(self.cols)] for _ in range(self.rows)]
        while True:
            matches = self.find_matches()
            if not matches:
                break
            self.clear_matches(matches)
            self.collapse()
            self.refill()
    def _random_candy(self) -> Candy:
        return random.randint(1, self.candy_types)
    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols
    def are_adjacent(self, r1: int, c1: int, r2: int, c2: int) -> bool:
        return abs(r1 - r2) + abs(c1 - c2) == 1
    def swap(self, r1: int, c1: int, r2: int, c2: int) -> None:
        self.grid[r1][c1], self.grid[r2][c2] = self.grid[r2][c2], self.grid[r1][c1]
    def find_matches(self) -> Set[Position]:
        """Find all cells that belong to 3+ horizontal or vertical matches."""
        matched: Set[Position] = set()
        for r in range(self.rows):
            c = 0
            while c < self.cols:
                candy = self.grid[r][c]
                if candy == 0:
                    c += 1
                    continue
                start = c
                while c + 1 < self.cols and self.grid[r][c + 1] == candy:
                    c += 1
                if c - start + 1 >= 3:
                    for cc in range(start, c + 1):
                        matched.add((r, cc))
                c += 1
        for c in range(self.cols):
            r = 0
            while r < self.rows:
                candy = self.grid[r][c]
                if candy == 0:
                    r += 1
                    continue
                start = r
                while r + 1 < self.rows and self.grid[r + 1][c] == candy:
                    r += 1
                if r - start + 1 >= 3:
                    for rr in range(start, r + 1):
                        matched.add((rr, c))
                r += 1
        return matched
    def clear_matches(self, matches: Set[Position]) -> int:
        """Clear matched candies by setting them to 0; return number cleared."""
        for r, c in matches:
            self.grid[r][c] = 0
        return len(matches)
    def collapse(self) -> None:
        """Apply gravity so candies fall down into empty spaces."""
        for c in range(self.cols):
            column = [self.grid[r][c] for r in range(self.rows) if self.grid[r][c] != 0]
            missing = self.rows - len(column)
            new_column = [0] * missing + column
            for r in range(self.rows):
                self.grid[r][c] = new_column[r]
    def refill(self) -> None:
        """Fill empty spaces with new random candies."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == 0:
                    self.grid[r][c] = self._random_candy()
    def resolve_board(self) -> int:
        """
        Resolve all cascading matches in one deterministic loop:
        repeatedly find matches, clear them, collapse, refill, until stable.
        Returns the total number of candies cleared.
        """
        total_cleared = 0
        while True:
            matches = self.find_matches()
            if not matches:
                break
            total_cleared += self.clear_matches(matches)
            self.collapse()
            self.refill()
        return total_cleared
    def try_swap_and_resolve(self, r1: int, c1: int, r2: int, c2: int) -> Tuple[bool, int]:
        """
        Attempt a swap. If it creates a match, keep it and resolve cascades.
        Returns (valid_move, score_gained).
        """
        self.swap(r1, c1, r2, c2)
        if not self.find_matches():
            self.swap(r1, c1, r2, c2)
            return False, 0
        gained = self.resolve_board()
        return True, gained
    def has_any_valid_move(self) -> bool:
        """Check whether any adjacent swap can produce a match."""
        for r in range(self.rows):
            for c in range(self.cols):
                if c + 1 < self.cols:
                    self.swap(r, c, r, c + 1)
                    valid = bool(self.find_matches())
                    self.swap(r, c, r, c + 1)
                    if valid:
                        return True
                if r + 1 < self.rows:
                    self.swap(r, c, r + 1, c)
                    valid = bool(self.find_matches())
                    self.swap(r, c, r + 1, c)
                    if valid:
                        return True
        return False