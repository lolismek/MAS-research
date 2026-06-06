'''
Game class manages the overall game flow and player interaction.
'''
from chessboard import ChessBoard
class Game:
    def __init__(self):
        self.chessboard = ChessBoard()
    def start_game(self):
        # Main game loop
        while True:
            self.chessboard.display_board()
            move = input(f"{self.chessboard.current_player}'s move: ")
            if self.process_input(move):
                self.chessboard.move_piece(move)
                if self.chessboard.is_checkmate():
                    print(f"Checkmate! {self.chessboard.current_player} wins!")
                    break
                elif self.chessboard.is_stalemate():
                    print("Stalemate! It's a draw!")
                    break
                self.switch_player()
    def process_input(self, move):
        # Parse and validate player input
        # For simplicity, assume input is always valid for now
        return True
    def switch_player(self):
        # Switch the active player
        self.chessboard.current_player = 'black' if self.chessboard.current_player == 'white' else 'white'