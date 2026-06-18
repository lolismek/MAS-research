'''
Main entry point for the terminal Wordle game.
'''
from wordle_game import WordleGame
def main():
    """Run the terminal Wordle game."""
    game = WordleGame()
    game.play()
if __name__ == "__main__":
    main()