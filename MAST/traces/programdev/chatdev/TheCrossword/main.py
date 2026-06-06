'''
Main application file for the crossword puzzle. Initializes the GUI and manages user interactions.
'''
import tkinter as tk
from tkinter import messagebox  # Add this line to import the messagebox module
from grid import CrosswordGrid
from clue import Clue, load_clues
class CrosswordApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Crossword Puzzle")
        self.grid = CrosswordGrid(10, 10)  # Example grid size
        self.clues = load_clues()
        self.create_widgets()
    def create_widgets(self):
        self.canvas = tk.Canvas(self.master, width=300, height=300)
        self.canvas.grid(row=0, column=0, columnspan=2)
        self.display_clues()
        self.entry = tk.Entry(self.master)
        self.entry.grid(row=1, column=0)
        self.submit_button = tk.Button(self.master, text="Submit", command=self.submit_word)
        self.submit_button.grid(row=1, column=1)
    def display_clues(self):
        clue_text = "\n".join([f"{clue.number}. {clue.text}" for clue in self.clues])
        self.clue_label = tk.Label(self.master, text=clue_text)
        self.clue_label.grid(row=2, column=0, columnspan=2)
    def submit_word(self):
        user_input = self.entry.get()
        try:
            # Assume input format: "1 across WORD"
            parts = user_input.split()
            if len(parts) != 3:
                raise ValueError("Invalid input format. Please use 'number direction WORD'.")
            clue_number = int(parts[0])
            direction = parts[1].lower()
            word = parts[2]
            if direction not in ['across', 'down']:
                raise ValueError("Invalid direction. Please use 'across' or 'down'.")
            clue = next((c for c in self.clues if c.number == clue_number and c.direction == direction), None)
            if clue is None:
                raise ValueError("Clue not found. Please check the clue number and direction.")
            if self.grid.validate_word(clue, word):
                self.grid.place_word(clue, word)
                self.check_completion()
            else:
                raise ValueError("Word does not fit the clue. Please try again.")
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
    def check_completion(self):
        if self.grid.is_complete():
            messagebox.showinfo("Congratulations!", "You have completed the crossword!")
if __name__ == "__main__":
    root = tk.Tk()
    app = CrosswordApp(root)
    root.mainloop()