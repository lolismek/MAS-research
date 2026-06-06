'''
Main application file for the Puzzle Game. Initializes the game and GUI.
'''
import tkinter as tk
from puzzle import Puzzle
from daily_puzzle import DailyPuzzle
class PuzzleGameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Puzzle Game")
        self.puzzle = DailyPuzzle().generate_puzzle()
        self.selected_words = []
        self.mistakes = 0
        self.setup_gui()
    def setup_gui(self):
        # Create the grid of buttons
        self.buttons = []
        for i in range(4):
            row = []
            for j in range(4):
                btn = tk.Button(self.root, text=self.puzzle.words[i*4+j], command=lambda i=i, j=j: self.select_word(i, j))
                btn.grid(row=i, column=j, padx=5, pady=5, sticky="nsew")
                row.append(btn)
            self.buttons.append(row)
        # Create feedback label
        self.feedback_label = tk.Label(self.root, text="")
        self.feedback_label.grid(row=5, column=0, columnspan=4)
        # Create reset button
        self.reset_button = tk.Button(self.root, text="Reset", command=self.reset_game)
        self.reset_button.grid(row=6, column=0, columnspan=4)
    def select_word(self, i, j):
        # Logic for selecting a word and checking if a group is correct
        word = self.puzzle.words[i*4+j]
        if word not in self.selected_words:
            self.selected_words.append(word)
            self.buttons[i][j].config(state="disabled")
        if len(self.selected_words) == 4:
            category, color = self.puzzle.check_group(self.selected_words)
            if category:
                self.feedback_label.config(text=f"Correct! Category: {category}", fg=color)
                self.puzzle.remove_correct_group(self.selected_words)
                for word in self.selected_words:
                    for row in self.buttons:
                        for btn in row:
                            if btn['text'] == word:
                                btn.config(text="", state="disabled")
            else:
                self.mistakes += 1
                self.feedback_label.config(text=f"Incorrect! Mistakes: {self.mistakes}/4")
                if self.mistakes >= 4:
                    self.feedback_label.config(text="Game Over! Too many mistakes.")
                    self.disable_all_buttons()
            self.selected_words = []
    def disable_all_buttons(self):
        for row in self.buttons:
            for btn in row:
                btn.config(state="disabled")
    def reset_game(self):
        # Logic to reset the game
        self.puzzle = DailyPuzzle().generate_puzzle()
        self.selected_words = []
        self.mistakes = 0
        self.feedback_label.config(text="")
        for i in range(4):
            for j in range(4):
                self.buttons[i][j].config(text=self.puzzle.words[i*4+j], state="normal")
if __name__ == "__main__":
    root = tk.Tk()
    app = PuzzleGameApp(root)
    root.mainloop()