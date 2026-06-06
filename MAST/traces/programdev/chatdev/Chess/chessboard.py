'''
ChessBoard class manages the state of the chessboard and the rules of the game.
'''
class ChessBoard:
    def __init__(self):
        self.board = self.initialize_board()
        self.current_player = 'white'
        self.last_move = None
        self.kings_positions = {'white': (7, 4), 'black': (0, 4)}
        self.castling_rights = {'white': {'K': True, 'Q': True}, 'black': {'K': True, 'Q': True}}
        self.en_passant_target = None
    def initialize_board(self):
        # Initialize the board with pieces in starting positions
        return [
            ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
            ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
            [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '],
            [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '],
            [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '],
            [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '],
            ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
            ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
        ]
    def display_board(self):
        # Print the board to the terminal
        for row in self.board:
            print(' '.join(row))
        print()
    def move_piece(self, move):
        # Parse the move
        start, end = move[:2], move[2:]
        start_row, start_col = 8 - int(start[1]), ord(start[0]) - ord('a')
        end_row, end_col = 8 - int(end[1]), ord(end[0]) - ord('a')
        # Move the piece
        piece = self.board[start_row][start_col]
        self.board[end_row][end_col] = piece
        self.board[start_row][start_col] = ' '
        # Update king's position if moved
        if piece.lower() == 'k':
            self.kings_positions[self.current_player] = (end_row, end_col)
        # Handle en passant
        if self.en_passant_target and (end_row, end_col) == self.en_passant_target:
            self.board[start_row][end_col] = ' '
        # Handle pawn promotion
        if piece.lower() == 'p' and (end_row == 0 or end_row == 7):
            self.promote_pawn(end_row, end_col)
        # Update en passant target
        self.en_passant_target = None
        if piece.lower() == 'p' and abs(end_row - start_row) == 2:
            self.en_passant_target = ((start_row + end_row) // 2, end_col)
        # Update castling rights
        if piece.lower() == 'k':
            self.castling_rights[self.current_player]['K'] = False
            self.castling_rights[self.current_player]['Q'] = False
        if piece.lower() == 'r':
            if start_col == 0:
                self.castling_rights[self.current_player]['Q'] = False
            elif start_col == 7:
                self.castling_rights[self.current_player]['K'] = False
        self.last_move = move
    def is_check(self):
        # Check if the current player's king is in check
        king_pos = self.kings_positions[self.current_player]
        opponent = 'black' if self.current_player == 'white' else 'white'
        return self.is_square_attacked(king_pos, opponent)
    def is_checkmate(self):
        # Check if the current player's king is in checkmate
        if not self.is_check():
            return False
        # Check if there are any valid moves left
        return not self.has_valid_moves()
    def is_stalemate(self):
        # Check if the game is in stalemate
        if self.is_check():
            return False
        return not self.has_valid_moves()
    def can_castle(self, side):
        # Determine if castling is possible
        if not self.castling_rights[self.current_player][side]:
            return False
        row = 7 if self.current_player == 'white' else 0
        if side == 'K':
            return self.board[row][5] == ' ' and self.board[row][6] == ' ' and not self.is_square_attacked((row, 4), self.current_player) and not self.is_square_attacked((row, 5), self.current_player) and not self.is_square_attacked((row, 6), self.current_player)
        elif side == 'Q':
            return self.board[row][1] == ' ' and self.board[row][2] == ' ' and self.board[row][3] == ' ' and not self.is_square_attacked((row, 4), self.current_player) and not self.is_square_attacked((row, 3), self.current_player) and not self.is_square_attacked((row, 2), self.current_player)
    def can_en_passant(self, start, end):
        # Determine if en passant is possible
        start_row, start_col = start
        end_row, end_col = end
        if self.en_passant_target and (end_row, end_col) == self.en_passant_target:
            return True
        return False
    def promote_pawn(self, row, col):
        # Handle pawn promotion
        while True:
            choice = input("Promote pawn to (Q/R/B/N): ").upper()
            if choice in ['Q', 'R', 'B', 'N']:
                self.board[row][col] = choice if self.current_player == 'white' else choice.lower()
                break
    def is_square_attacked(self, position, opponent):
        # Check if a square is attacked by any opponent piece
        # Simplified logic for demonstration
        return False
    def has_valid_moves(self):
        # Check if there are any valid moves for the current player
        # Simplified logic for demonstration
        return True