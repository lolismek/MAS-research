'''
Main entry point for the Match-3 puzzle game.
'''
from game_controller import GameController
def main() -> None:
    """Start the game application."""
    game = GameController()
    game.run()
if __name__ == "__main__":
    main()