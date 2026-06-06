'''
Main file for the Strands game application. Manages the game logic and GUI.
'''
import tkinter as tk
from strand import Strand
from word_validator import WordValidator
class StrandsGame:
    def __init__(self, master):
        self.master = master
        self.master.title("Strands Game")
        # Initialize game components
        self.strands = [Strand("he"), Strand("llo"), Strand("wor"), Strand("ld")]
        self.validator = WordValidator(["hello", "world", "helloworld"])
        self.current_combination = ""
        # Create GUI components
        self.create_widgets()
    def create_widgets(self):
        self.strand_buttons = []
        for strand in self.strands:
            button = tk.Button(self.master, text=strand.get_text(), command=lambda s=strand: self.check_merge(s))
            button.pack(side=tk.LEFT)
            self.strand_buttons.append(button)
        self.feedback_label = tk.Label(self.master, text="Combine strands to form words!")
        self.feedback_label.pack()
        self.reset_button = tk.Button(self.master, text="Reset", command=self.reset_game)
        self.reset_button.pack()
    def check_merge(self, strand):
        # Append the selected strand to the current combination
        self.current_combination += strand.get_text()
        # Check if the current combination is valid
        if self.validator.is_valid(self.current_combination):
            self.update_feedback("Valid merge!")
        else:
            self.update_feedback("Invalid merge, try again.")
    def update_feedback(self, message):
        self.feedback_label.config(text=message)
    def reset_game(self):
        self.current_combination = ""
        self.update_feedback("Combine strands to form words!")
if __name__ == "__main__":
    root = tk.Tk()
    game = StrandsGame(root)
    root.mainloop()