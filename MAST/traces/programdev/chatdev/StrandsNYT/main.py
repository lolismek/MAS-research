'''
Main application file for the NYT Strands puzzle game. Initializes the GUI and manages the game loop.
'''
import tkinter as tk
from game_board import GameBoard
from hint_system import HintSystem
class StrandsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NYT Strands Puzzle")
        self.game_board = GameBoard(self.root, self.on_word_found)
        self.hint_system = HintSystem()
        self.setup_gui()
    def setup_gui(self):
        self.hint_label = tk.Label(self.root, text="Hints: 0")
        self.hint_label.pack()
        self.game_board.pack()
    def on_word_found(self, word_type):
        if word_type == "non-theme":
            self.hint_system.increment_non_theme_count()
            hints = self.hint_system.get_hints()
            self.hint_label.config(text=f"Hints: {hints}")
    def run(self):
        self.root.mainloop()
if __name__ == "__main__":
    root = tk.Tk()
    app = StrandsApp(root)
    app.run()