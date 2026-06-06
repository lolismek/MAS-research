'''
Manages the graphical user interface for the Minesweeper game.
'''
import tkinter as tk
from tkinter import messagebox
class MinesweeperGUI:
    def __init__(self, master, game):
        self.master = master
        self.game = game
        self.buttons = [[None for _ in range(game.cols)] for _ in range(game.rows)]
        self.create_widgets()
        self.update_display()
    def create_widgets(self):
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                btn = tk.Button(self.master, width=2, height=1, command=lambda r=r, c=c: self.on_cell_click(r, c))
                btn.bind("<Button-3>", lambda event, r=r, c=c: self.on_right_click(event, r, c))
                btn.grid(row=r, column=c)
                self.buttons[r][c] = btn
    def update_display(self):
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                if self.game.revealed[r][c]:
                    if self.game.board[r][c] == -1:
                        self.buttons[r][c].config(text="*", bg="red")
                    else:
                        self.buttons[r][c].config(text=str(self.game.board[r][c]), bg="light grey")
                elif self.game.flags[r][c]:
                    self.buttons[r][c].config(text="F", bg="yellow")
                else:
                    self.buttons[r][c].config(text="", bg="SystemButtonFace")
    def on_cell_click(self, row, col):
        if self.game.game_over:
            messagebox.showinfo("Game Over", "You hit a mine!")
            return
        self.game.reveal_cell(row, col)
        self.update_display()
        if self.game.game_over:
            messagebox.showinfo("Game Over", "You hit a mine!")
        elif self.game.check_win():
            messagebox.showinfo("Congratulations", "You won the game!")
    def on_right_click(self, event, row, col):
        self.game.flag_cell(row, col)
        self.update_display()