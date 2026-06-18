'''
Game logic for a standard Gomoku game on a 15x15 board.
'''
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
BOARD_SIZE = 15
EMPTY = 0
BLACK = 1
WHITE = 2
@dataclass
class GomokuGame:
    """Encapsulates Gomoku rules, state, and win detection."""
    board_size: int = BOARD_SIZE
    board: List[List[int]] = field(
        default_factory=lambda: [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    )
    current_player: int = BLACK
    winner: Optional[int] = None
    last_move: Optional[Tuple[int, int]] = None
    move_count: int = 0
    def reset(self) -> None:
        """Reset the game to its initial state."""
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]
        self.current_player = BLACK
        self.winner = None
        self.last_move = None
        self.move_count = 0
    def is_valid_move(self, row: int, col: int) -> bool:
        """Return True if a move is legal."""
        if self.winner is not None:
            return False
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            return False
        return self.board[row][col] == EMPTY
    def make_move(self, row: int, col: int) -> bool:
        """
        Place a stone for the current player at (row, col).
        Returns True if move was successful.
        """
        if not self.is_valid_move(row, col):
            return False
        self.board[row][col] = self.current_player
        self.last_move = (row, col)
        self.move_count += 1
        if self.check_winner(row, col):
            self.winner = self.current_player
        else:
            self.current_player = WHITE if self.current_player == BLACK else BLACK
        return True
    def check_winner(self, row: int, col: int) -> bool:
        """Check whether the last move at (row, col) creates a five-in-a-row."""
        player = self.board[row][col]
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dr, dc in directions:
            count = 1
            count += self._count_direction(row, col, dr, dc, player)
            count += self._count_direction(row, col, -dr, -dc, player)
            if count >= 5:
                return True
        return False
    def _count_direction(self, row: int, col: int, dr: int, dc: int, player: int) -> int:
        """Count consecutive stones of the same player in one direction."""
        r, c = row + dr, col + dc
        count = 0
        while (
            0 <= r < self.board_size
            and 0 <= c < self.board_size
            and self.board[r][c] == player
        ):
            count += 1
            r += dr
            c += dc
        return count
    def is_draw(self) -> bool:
        """Return True if the board is full and there is no winner."""
        return self.winner is None and self.move_count >= self.board_size * self.board_size
    def get_cell(self, row: int, col: int) -> int:
        """Return the value stored at a board cell."""
        return self.board[row][col]
    def run_cli(self) -> None:
        """Run a simple command-line version of Gomoku."""
        print("Gomoku (15x15)")
        print("Enter moves as: row col  (0-based indices, e.g., 7 7)")
        print("Type 'quit' to exit.\n")
        while True:
            self._print_board()
            if self.winner is not None:
                print(f"\nWinner: {'Black' if self.winner == BLACK else 'White'}")
                return
            if self.is_draw():
                print("\nDraw game.")
                return
            player_name = "Black" if self.current_player == BLACK else "White"
            try:
                raw = input(f"{player_name}'s move: ").strip().lower()
            except EOFError:
                print("\nNo input available. Exiting CLI gracefully.")
                return
            if raw in {"quit", "exit"}:
                print("Goodbye.")
                return
            try:
                row_s, col_s = raw.split()
                row, col = int(row_s), int(col_s)
            except ValueError:
                print("Invalid input. Please enter two integers like: 7 7")
                continue
            if not self.make_move(row, col):
                print("Illegal move. Try again.")
    def _print_board(self) -> None:
        """Print the current board state to the console."""
        header = "   " + " ".join(f"{i:2d}" for i in range(self.board_size))
        print("\n" + header)
        for r in range(self.board_size):
            row_cells = []
            for c in range(self.board_size):
                cell = self.board[r][c]
                if cell == BLACK:
                    row_cells.append("● ")
                elif cell == WHITE:
                    row_cells.append("○ ")
                else:
                    row_cells.append("· ")
            print(f"{r:2d} " + "".join(row_cells))