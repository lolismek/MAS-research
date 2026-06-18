'''
Main entry point for the Gomoku application.
'''
import sys
from gomoku_game import GomokuGame
from gomoku_gui import GomokuGUI, TK_AVAILABLE
def main():
    """Launch the Gomoku application with GUI when available, otherwise use CLI."""
    # Prefer GUI when possible, but fall back safely to CLI in non-interactive environments.
    if TK_AVAILABLE:
        try:
            app = GomokuGUI()
            app.run()
            return
        except Exception:
            # If GUI cannot be initialized in the current environment, fall back to CLI.
            pass
    # Only run the CLI when stdin is interactive; otherwise exit gracefully.
    if not sys.stdin or not sys.stdin.isatty():
        print("Gomoku is ready, but no interactive input is available in this environment.")
        return
    game = GomokuGame()
    game.run_cli()
if __name__ == "__main__":
    main()