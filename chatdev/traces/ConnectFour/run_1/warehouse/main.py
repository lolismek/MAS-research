'''
Main entry point for the Connect Four console application.
'''
from game import ConnectFourGame
from cli import ConnectFourCLI
def main():
    """Launch the Connect Four game."""
    game = ConnectFourGame()
    app = ConnectFourCLI(game)
    app.run()
if __name__ == "__main__":
    main()