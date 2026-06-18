'''
Entry point for the crossword puzzle application.
This version gracefully handles environments where Tkinter is unavailable
(e.g., Python builds without _tkinter). In that case, it falls back to a
console-based crossword game so the application can still run smoothly.
'''
from puzzle import build_default_puzzle
def main():
    """Launch the crossword puzzle application."""
    puzzle = build_default_puzzle()
    try:
        import tkinter as tk
        from crossword_gui import CrosswordGUI
    except Exception:
        # Fallback to a console interface if Tkinter is unavailable.
        from crossword_cli import CrosswordCLI
        app = CrosswordCLI(puzzle)
        app.run()
        return
    try:
        root = tk.Tk()
    except Exception:
        # If the Tk subsystem cannot initialize, use the console fallback.
        from crossword_cli import CrosswordCLI
        app = CrosswordCLI(puzzle)
        app.run()
        return
    app = CrosswordGUI(root, puzzle)
    root.mainloop()
if __name__ == "__main__":
    main()