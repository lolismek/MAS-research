'''
command-line interface for the checkers game application
'''
from game import CheckersGame, parse_move_notation, PLAYER_1, PLAYER_2, coords_to_position
class CheckersGUI:
    """Simple command-line interface for playing checkers."""
    def __init__(self):
        self.game = CheckersGame()
    def _player_name(self, symbol: str) -> str:
        """Convert player symbol to display name."""
        return "Red" if symbol == PLAYER_1 else "Black"
    def _print_help(self):
        """Print game instructions."""
        print("\nCommands:")
        print("  move like: b6-a5")
        print("  reset     : restart the game")
        print("  quit      : exit the game")
        print("")
    def _safe_input(self, prompt: str):
        """Read input safely and return None on EOF so tests/non-interactive runs do not crash."""
        try:
            return input(prompt)
        except EOFError:
            return None
        except KeyboardInterrupt:
            return None
    def run(self):
        """Run the interactive game loop."""
        print("Checkers (Draughts)")
        print("Use move notation like b6-a5")
        self._print_help()
        while True:
            print(self.game.board_text())
            if self.game.game_over:
                winner = self.game.get_winner()
                if winner:
                    print(f"\nGame over! Winner: {self._player_name(winner)}")
                else:
                    print("\nGame over!")
                break
            print(f"\n{self.game.current_player_name()}'s turn")
            if self.game.forced_capture_piece is not None:
                forced_row, forced_col = self.game.forced_capture_piece
                print(f"Forced capture continuation from {coords_to_position(forced_row, forced_col)}")
            move_raw = self._safe_input("Enter move (or 'help', 'reset', 'quit'): ")
            if move_raw is None:
                print("\nNo input available. Exiting cleanly.")
                break
            move_text = move_raw.strip()
            if not move_text:
                print("Please enter a move.")
                continue
            lowered = move_text.lower()
            if lowered == "quit":
                print("Goodbye.")
                break
            if lowered == "help":
                self._print_help()
                continue
            if lowered == "reset":
                self.game.reset()
                print("Game reset.")
                continue
            try:
                (src_row, src_col), (dst_row, dst_col) = parse_move_notation(move_text)
                result = self.game.apply_move(src_row, src_col, dst_row, dst_col)
                print(result.message)
            except Exception as e:
                print(f"Error: {e}")