'''
Handles the creation and management of the game board, including placing words and checking for completion.
'''
import tkinter as tk
from word import Word
class GameBoard(tk.Frame):
    def __init__(self, master, word_found_callback):
        super().__init__(master)
        self.word_found_callback = word_found_callback
        self.grid_size = (6, 8)
        self.words = []
        self.create_board()
    def create_board(self):
        self.cells = [[tk.Button(self, text='', width=4, height=2) for _ in range(self.grid_size[1])] for _ in range(self.grid_size[0])]
        for i, row in enumerate(self.cells):
            for j, cell in enumerate(row):
                cell.grid(row=i, column=j)
                cell.config(command=lambda i=i, j=j: self.on_cell_click(i, j))
    def on_cell_click(self, i, j):
        # Logic to handle cell click and check for word completion
        for word in self.words:
            if (i, j) in word.get_positions():
                self.highlight_word(word)
                self.word_found_callback(word.word_type)
                break
    def place_spangram(self, word):
        positions = word.get_positions()
        # Check if the word fits within the grid boundaries
        if not all(0 <= pos[0] < self.grid_size[0] and 0 <= pos[1] < self.grid_size[1] for pos in positions):
            return  # Word does not fit within the grid
        # Check for overlap with existing words
        for pos in positions:
            i, j = pos
            if self.cells[i][j]['text'] != '':
                return  # Overlap detected
        # Ensure the spangram touches two opposite sides
        if word.direction == 'horizontal':
            if positions[0][1] == 0 and positions[-1][1] == self.grid_size[1] - 1:
                self.place_word(word)
        elif word.direction == 'vertical':
            if positions[0][0] == 0 and positions[-1][0] == self.grid_size[0] - 1:
                self.place_word(word)
        elif word.direction == 'diagonal':
            if (positions[0][0] == 0 and positions[-1][0] == self.grid_size[0] - 1) or \
               (positions[0][1] == 0 and positions[-1][1] == self.grid_size[1] - 1):
                self.place_word(word)
    def place_word(self, word):
        # Logic to place a word on the board
        positions = word.get_positions()
        for pos in positions:
            i, j = pos
            self.cells[i][j].config(text=word.text[positions.index(pos)])
        self.words.append(word)
    def check_completion(self):
        # Logic to check if the board is fully completed
        for row in self.cells:
            for cell in row:
                if cell['text'] == '':
                    return False
        return True
    def highlight_word(self, word):
        color = 'blue' if word.word_type == 'theme' else 'yellow'
        for pos in word.get_positions():
            i, j = pos
            self.cells[i][j].config(bg=color)