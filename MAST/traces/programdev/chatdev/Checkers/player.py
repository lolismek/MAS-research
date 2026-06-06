'''
Player class to represent a player in the game.
'''
from piece import Piece
class Player:
    def __init__(self, color):
        self.color = color
        self.pieces = []
    def make_move(self, board, from_pos, to_pos):
        '''
        Move a piece from one position to another, capturing if necessary.
        '''
        piece = board.grid[from_pos[0]][from_pos[1]]
        if piece and piece.color == self.color:
            # Check if the move is valid
            if self.is_valid_move(board, from_pos, to_pos):
                # Move the piece
                board.grid[to_pos[0]][to_pos[1]] = piece
                board.grid[from_pos[0]][from_pos[1]] = None
                piece.position = to_pos
                # Check for capture
                if abs(from_pos[0] - to_pos[0]) == 2:
                    capture_pos = ((from_pos[0] + to_pos[0]) // 2, (from_pos[1] + to_pos[1]) // 2)
                    board.grid[capture_pos[0]][capture_pos[1]] = None
                # Check for kinging
                if (self.color == 'white' and to_pos[0] == 0) or (self.color == 'black' and to_pos[0] == 7):
                    piece.king = True
                return True
        return False
    def is_valid_move(self, board, from_pos, to_pos):
        '''
        Validate the move according to the rules of Checkers.
        '''
        piece = board.grid[from_pos[0]][from_pos[1]]
        if not piece:
            return False
        direction = -1 if piece.color == 'white' else 1
        if piece.king:
            directions = [1, -1]
        else:
            directions = [direction]
        # Normal move
        if (to_pos[0] - from_pos[0] in directions) and abs(to_pos[1] - from_pos[1]) == 1:
            return board.grid[to_pos[0]][to_pos[1]] is None
        # Capture move
        if (to_pos[0] - from_pos[0] in [2 * d for d in directions]) and abs(to_pos[1] - from_pos[1]) == 2:
            capture_pos = ((from_pos[0] + to_pos[0]) // 2, (from_pos[1] + to_pos[1]) // 2)
            capture_piece = board.grid[capture_pos[0]][capture_pos[1]]
            return capture_piece and capture_piece.color != piece.color and board.grid[to_pos[0]][to_pos[1]] is None
        return False