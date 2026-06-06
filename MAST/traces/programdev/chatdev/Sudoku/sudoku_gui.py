'''
Defines the SudokuGUI class for managing the graphical user interface.
'''
import tkinter as tk
from tkinter import messagebox
from sudoku_game import SudokuGame
class SudokuGUI:
    def __init__(self):
        '''
        Initialize the GUI with a SudokuGame instance.
        '''
        self.game = SudokuGame()
        self.root = tk.Tk()
        self.root.title("Sudoku")
        self.cells = [[None for _ in range(9)] for _ in range(9)]
        self.create_grid()
    def create_grid(self):
        '''
        Create the 9x9 grid of entry widgets for the Sudoku game.
        '''
        for row in range(9):
            for col in range(9):
                entry = tk.Entry(self.root, width=2, font=('Arial', 18), justify='center')
                entry.grid(row=row, column=col, padx=5, pady=5)
                entry.bind('<FocusOut>', lambda e, r=row, c=col: self.update_value(r, c))
                self.cells[row][col] = entry
    def update_value(self, row, col):
        '''
        Update the value in the grid based on user input.
        '''
        try:
            value = int(self.cells[row][col].get())
            if not self.game.input_value(row, col, value):
                self.cells[row][col].delete(0, tk.END)
                self.cells[row][col].insert(0, '')
            else:
                self.check_completion()
        except ValueError:
            self.cells[row][col].delete(0, tk.END)
    def check_completion(self):
        '''
        Check if the Sudoku puzzle is completed and notify the user.
        '''
        if self.game.check_completion():
            messagebox.showinfo("Sudoku", "Congratulations! You have completed the puzzle!")
    def run(self):
        '''
        Run the main loop of the Tkinter application.
        '''
        self.root.mainloop()