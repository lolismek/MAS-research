'''
Graphical User Interface for the Mastermind game.
'''
import tkinter as tk
from mastermind import MastermindGame
class MastermindGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mastermind Game")
        self.game = MastermindGame()
        self.guess_entries = []
        self.feedback_labels = []
    def setup_gui(self):
        tk.Label(self.root, text="Enter your guess:").grid(row=0, column=0, columnspan=2)
        for i in range(self.game.sequence_length):
            entry = tk.Entry(self.root, width=3)
            entry.grid(row=1, column=i)
            self.guess_entries.append(entry)
        self.feedback_label = tk.Label(self.root, text="")
        self.feedback_label.grid(row=2, column=0, columnspan=self.game.sequence_length)
        submit_button = tk.Button(self.root, text="Submit Guess", command=self.submit_guess)
        submit_button.grid(row=3, column=0, columnspan=self.game.sequence_length)
        self.root.mainloop()
    def submit_guess(self):
        guess = [entry.get().upper() for entry in self.guess_entries]  # Ensure uppercase for consistency
        feedback, win = self.game.check_guess(guess)
        self.feedback_label.config(text=feedback)
        if win:
            self.feedback_label.config(text="Congratulations! You've cracked the code!")
            for entry in self.guess_entries:
                entry.config(state='disabled')