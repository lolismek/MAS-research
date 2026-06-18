'''
checkers game logic and rules engine
'''
from dataclasses import dataclass
BOARD_SIZE = 8
EMPTY = "."
PLAYER_1 = "r"
PLAYER_2 = "b"
PLAYER_1_KING = "R"
PLAYER_2_KING = "B"
@dataclass(frozen=True)
class MoveResult:
    """Represents the outcome of attempting a move."""
    success: bool
    message: str = ""
def coords_to_position(row: int, col: int) -> str:
    """Convert board coordinates to human-readable notation like b6."""
    return f"{chr(ord('a') + col)}{BOARD_SIZE - row}"
def position_to_coords(pos: str):
    """Convert human-readable notation like b6 to board coordinates."""
    pos = pos.strip().lower()
    if len(pos) < 2:
        raise ValueError("Invalid position format.")
    col_char = pos[0]
    row_part = pos[1:]
    if not ('a' <= col_char <= 'h'):
        raise ValueError("Column must be between a and h.")
    if not row_part.isdigit():
        raise ValueError("Row must be numeric.")
    col = ord(col_char) - ord('a')
    row_num = int(row_part)
    if not (1 <= row_num <= BOARD_SIZE):
        raise ValueError("Row must be between 1 and 8.")
    row = BOARD_SIZE - row_num
    return row, col
def parse_move_notation(move_text: str):
    """Parse move notation like b6-a5 into source and destination coordinates."""
    move_text = move_text.strip()
    if "-" not in move_text:
        raise ValueError("Move must use '-' notation, e.g., b6-a5.")
    src_text, dst_text = move_text.split("-", 1)
    src = position_to_coords(src_text)
    dst = position_to_coords(dst_text)
    return src, dst
class CheckersGame:
    """Implements standard 8x8 checkers rules, including forced captures and multi-capture continuation."""
    def __init__(self):
        self.board = self._create_initial_board()
        self.current_player = PLAYER_1
        self.game_over = False
        self.winner = None
        self.forced_capture_piece = None
    def _create_initial_board(self):
        """Create the standard starting board."""
        board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        for row in range(3):
            for col in range(BOARD_SIZE):
                if (row + col) % 2 == 1:
                    board[row][col] = PLAYER_2
        for row in range(5, 8):
            for col in range(BOARD_SIZE):
                if (row + col) % 2 == 1:
                    board[row][col] = PLAYER_1
        return board
    def reset(self):
        """Reset the game to the starting position."""
        self.board = self._create_initial_board()
        self.current_player = PLAYER_1
        self.game_over = False
        self.winner = None
        self.forced_capture_piece = None
    def piece_owner(self, piece: str):
        """Return the owner of a piece, or None for empty squares."""
        if piece in (PLAYER_1, PLAYER_1_KING):
            return PLAYER_1
        if piece in (PLAYER_2, PLAYER_2_KING):
            return PLAYER_2
        return None
    def is_king(self, piece: str):
        """Check whether a piece is a king."""
        return piece in (PLAYER_1_KING, PLAYER_2_KING)
    def _directions_for_piece(self, piece: str):
        """Get movement directions for a piece."""
        if piece == PLAYER_1:
            return [(-1, -1), (-1, 1)]
        if piece == PLAYER_2:
            return [(1, -1), (1, 1)]
        return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    def _enemy_pieces(self, player: str):
        """Return the set of enemy piece symbols for a player."""
        if player == PLAYER_1:
            return {PLAYER_2, PLAYER_2_KING}
        return {PLAYER_1, PLAYER_1_KING}
    def _in_bounds(self, row: int, col: int):
        """Check if a position is inside the board."""
        return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE
    def get_valid_moves_for_piece(self, row: int, col: int):
        """
        Return valid moves for a piece.
        Result format:
        {
            "simple": [(r, c), ...],
            "captures": [((mid_r, mid_c), (dest_r, dest_c)), ...]
        }
        """
        piece = self.board[row][col]
        if piece == EMPTY:
            return {"simple": [], "captures": []}
        owner = self.piece_owner(piece)
        if owner != self.current_player:
            return {"simple": [], "captures": []}
        simple_moves = []
        captures = []
        dirs = self._directions_for_piece(piece)
        enemies = self._enemy_pieces(owner)
        for dr, dc in dirs:
            r1, c1 = row + dr, col + dc
            if self._in_bounds(r1, c1):
                if self.board[r1][c1] == EMPTY:
                    simple_moves.append((r1, c1))
                elif self.board[r1][c1] in enemies:
                    r2, c2 = row + 2 * dr, col + 2 * dc
                    if self._in_bounds(r2, c2) and self.board[r2][c2] == EMPTY:
                        captures.append(((r1, c1), (r2, c2)))
        return {"simple": simple_moves, "captures": captures}
    def _has_any_capture_for_player(self, player: str):
        """Determine if the given player has at least one capture available."""
        current = self.current_player
        self.current_player = player
        try:
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    piece = self.board[r][c]
                    if self.piece_owner(piece) == player:
                        moves = self.get_valid_moves_for_piece(r, c)
                        if moves["captures"]:
                            return True
            return False
        finally:
            self.current_player = current
    def has_any_valid_move(self, player: str):
        """Determine if the given player has any legal move."""
        current = self.current_player
        self.current_player = player
        try:
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    piece = self.board[r][c]
                    if self.piece_owner(piece) == player:
                        moves = self.get_valid_moves_for_piece(r, c)
                        if moves["simple"] or moves["captures"]:
                            return True
            return False
        finally:
            self.current_player = current
    def _available_captures_from(self, row: int, col: int):
        """Return capture destinations for a specific piece, ignoring turn restrictions."""
        piece = self.board[row][col]
        if piece == EMPTY:
            return []
        owner = self.piece_owner(piece)
        if owner is None:
            return []
        dirs = self._directions_for_piece(piece)
        enemies = self._enemy_pieces(owner)
        caps = []
        for dr, dc in dirs:
            r1, c1 = row + dr, col + dc
            r2, c2 = row + 2 * dr, col + 2 * dc
            if self._in_bounds(r2, c2) and self._in_bounds(r1, c1):
                if self.board[r1][c1] in enemies and self.board[r2][c2] == EMPTY:
                    caps.append(((r1, c1), (r2, c2)))
        return caps
    def apply_move(self, src_row: int, src_col: int, dst_row: int, dst_col: int):
        """Apply a move if it is legal."""
        if self.game_over:
            return MoveResult(False, "Game is over. Please reset to play again.")
        if not self._in_bounds(src_row, src_col) or not self._in_bounds(dst_row, dst_col):
            return MoveResult(False, "Move is out of bounds.")
        if self.forced_capture_piece is not None and (src_row, src_col) != self.forced_capture_piece:
            return MoveResult(False, "You must continue capturing with the same piece.")
        piece = self.board[src_row][src_col]
        if piece == EMPTY:
            return MoveResult(False, "No piece at source square.")
        if self.piece_owner(piece) != self.current_player:
            return MoveResult(False, "It is not that piece's turn.")
        if self.board[dst_row][dst_col] != EMPTY:
            return MoveResult(False, "Destination square is not empty.")
        legal = self.get_valid_moves_for_piece(src_row, src_col)
        capture_move = None
        if (dst_row, dst_col) in legal["simple"]:
            if self.forced_capture_piece is not None:
                return MoveResult(False, "A capture chain is active and you must keep capturing.")
            if self._has_any_capture_for_player(self.current_player):
                return MoveResult(False, "A capture is available and must be taken.")
        else:
            for cap in legal["captures"]:
                if cap[1] == (dst_row, dst_col):
                    capture_move = cap
                    break
            if capture_move is None:
                return MoveResult(False, "Illegal move.")
        if capture_move:
            mid_r, mid_c = capture_move[0]
            self.board[mid_r][mid_c] = EMPTY
        self.board[dst_row][dst_col] = piece
        self.board[src_row][src_col] = EMPTY
        became_king = False
        if piece == PLAYER_1 and dst_row == 0:
            self.board[dst_row][dst_col] = PLAYER_1_KING
            became_king = True
        elif piece == PLAYER_2 and dst_row == BOARD_SIZE - 1:
            self.board[dst_row][dst_col] = PLAYER_2_KING
            became_king = True
        if capture_move:
            continued_captures = self._available_captures_from(dst_row, dst_col)
            if continued_captures and not became_king:
                self.forced_capture_piece = (dst_row, dst_col)
                return MoveResult(True, "Capture applied successfully. Another capture is required from the same piece.")
        self.forced_capture_piece = None
        self.current_player = PLAYER_2 if self.current_player == PLAYER_1 else PLAYER_1
        if not self.has_any_valid_move(self.current_player):
            self.game_over = True
            self.winner = PLAYER_1 if self.current_player == PLAYER_2 else PLAYER_2
        return MoveResult(True, "Move applied successfully.")
    def board_text(self):
        """Return a text representation of the board."""
        lines = []
        header = "   " + " ".join(list("abcdefgh"))
        lines.append(header)
        for r in range(BOARD_SIZE):
            row_num = BOARD_SIZE - r
            line = [f"{row_num}  "]
            for c in range(BOARD_SIZE):
                line.append(self.board[r][c])
            lines.append(" ".join(line))
        return "\n".join(lines)
    def get_winner(self):
        """Return the winner symbol if the game is over."""
        return self.winner
    def current_player_name(self):
        """Human-readable current player name."""
        return "Red" if self.current_player == PLAYER_1 else "Black"