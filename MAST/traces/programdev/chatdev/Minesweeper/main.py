'''
Main entry point for the Minesweeper game application.
'''
import tkinter as tk
from minesweeper_game import MinesweeperGame
from minesweeper_gui import MinesweeperGUI
def main():
    root = tk.Tk()
    root.title("Minesweeper")
    # Set difficulty level
    difficulty = {
        "beginner": (9, 9, 10),
        "intermediate": (16, 16, 40),
        "expert": (16, 30, 99)
    }
    # Choose difficulty level
    level = "beginner"  # Change to "intermediate" or "expert" as needed
    rows, cols, mines = difficulty[level]
    game = MinesweeperGame(rows, cols, mines)
    gui = MinesweeperGUI(root, game)
    root.mainloop()
if __name__ == "__main__":
    main()