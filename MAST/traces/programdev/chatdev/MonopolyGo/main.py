'''
Main entry point for the Monopoly Go! game. Initializes the game and starts the game loop.
'''
from game import Game
def main():
    game = Game()
    game.start_game()
if __name__ == "__main__":
    main()