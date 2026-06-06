'''
Main file to run the chess game. It initializes the game and manages the game loop.
'''
from chessboard import ChessBoard
from game import Game
def main():
    game = Game()
    game.start_game()
if __name__ == "__main__":
    main()