'''
Console user interface for the Connect Four game.
'''
from game import ConnectFourGame
class ConnectFourCLI:
    """Simple terminal-based interface for Connect Four."""
    def __init__(self, game: ConnectFourGame):
        self.game = game
    def run(self) -> None:
        """Run the interactive game loop."""
        print("Welcome to Connect Four!")
        print(f"Players take turns choosing a column from 1 to {self.game.columns}.")
        print("Player 1 = X, Player 2 = O")
        print()
        while not self.game.game_over:
            print(self.game.render_board())
            print()
            prompt = f"Player {self.game.current_player} choose a column (1-{self.game.columns}): "
            try:
                user_input = input(prompt).strip()
            except EOFError:
                print("\nNo input detected. Exiting game.")
                break
            except KeyboardInterrupt:
                print("\nGame interrupted. Exiting.")
                break
            try:
                column = int(user_input) - 1
            except ValueError:
                print("Invalid input. Please enter a number.")
                print()
                continue
            if column < 0 or column >= self.game.columns:
                print(f"Invalid column. Please choose a number from 1 to {self.game.columns}.")
                print()
                continue
            success, message = self.game.drop_piece(column)
            print(message)
            print()
            if not success:
                continue
        print(self.game.render_board())
        if self.game.winner is not None:
            print(f"Game over! Player {self.game.winner} wins.")
        elif self.game.game_over:
            print("Game over! It's a draw.")