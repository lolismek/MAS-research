'''
Game logic for a standard Connect Four implementation.
'''
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
ROWS = 6
COLUMNS = 7
EMPTY = 0
PLAYER_ONE = 1
PLAYER_TWO = 2
@dataclass
class ConnectFourGame:
    """Encapsulates Connect Four state and rules."""
    rows: int = ROWS
    columns: int = COLUMNS
    board: List[List[int]] = field(default_factory=list)
    current_player: int = PLAYER_ONE
    winner: Optional[int] = None
    game_over: bool = False
    def __post_init__(self) -> None:
        """Initialize or normalize the board size."""
        if (
            not self.board
            or len(self.board) != self.rows
            or any(len(row) != self.columns for row in self.board)
        ):
            self.board = [[EMPTY for _ in range(self.columns)] for _ in range(self.rows)]
    def reset(self) -> None:
        """Reset the game to its initial state."""
        self.board = [[EMPTY] * self.columns for _ in range(self.rows)]
        self.current_player = PLAYER_ONE
        self.winner = None
        self.game_over = False
    def is_valid_column(self, column: int) -> bool:
        """Check if a column is in range and not full."""
        return 0 <= column < self.columns and self.board[0][column] == EMPTY
    def get_next_open_row(self, column: int) -> Optional[int]:
        """Return the lowest available row index for a column, or None if full."""
        for row in range(self.rows - 1, -1, -1):
            if self.board[row][column] == EMPTY:
                return row
        return None
    def drop_piece(self, column: int) -> Tuple[bool, str]:
        """
        Place a piece in the selected column.
        Returns (success, message).
        """
        if self.game_over:
            return False, "The game is over. Please restart to play again."
        if not isinstance(column, int):
            return False, "Invalid input. Please enter a column number."
        if column < 0 or column >= self.columns:
            return False, f"Invalid column. Please choose a number from 1 to {self.columns}."
        if not self.is_valid_column(column):
            return False, f"Column {column + 1} is invalid or full. Choose another column."
        row = self.get_next_open_row(column)
        if row is None:
            return False, f"Column {column + 1} is full. Choose another column."
        self.board[row][column] = self.current_player
        if self.check_win(self.current_player):
            self.winner = self.current_player
            self.game_over = True
            return True, f"Player {self.current_player} wins!"
        if self.is_board_full():
            self.game_over = True
            return True, "It's a draw!"
        self.current_player = PLAYER_TWO if self.current_player == PLAYER_ONE else PLAYER_ONE
        return True, "Move accepted."
    def is_board_full(self) -> bool:
        """Check whether the entire board is full."""
        return all(self.board[0][col] != EMPTY for col in range(self.columns))
    def check_win(self, player: int) -> bool:
        """Check horizontal, vertical, and both diagonal win conditions for a player."""
        # Horizontal
        for row in range(self.rows):
            for col in range(self.columns - 3):
                if all(self.board[row][col + i] == player for i in range(4)):
                    return True
        # Vertical
        for row in range(self.rows - 3):
            for col in range(self.columns):
                if all(self.board[row + i][col] == player for i in range(4)):
                    return True
        # Diagonal: / (rows decrease, columns increase)
        for row in range(3, self.rows):
            for col in range(self.columns - 3):
                if all(self.board[row - i][col + i] == player for i in range(4)):
                    return True
        # Diagonal: \ (rows increase, columns increase)
        for row in range(self.rows - 3):
            for col in range(self.columns - 3):
                if all(self.board[row + i][col + i] == player for i in range(4)):
                    return True
        return False
    def render_board(self) -> str:
        """Return a printable representation of the current board."""
        symbols = {
            EMPTY: ".",
            PLAYER_ONE: "X",
            PLAYER_TWO: "O",
        }
        lines = []
        lines.append("  ".join(str(i + 1) for i in range(self.columns)))
        for row in self.board:
            lines.append("  ".join(symbols[cell] for cell in row))
        return "\n".join(lines)