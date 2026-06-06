'''
Contains the GUI logic for Connect Four using tkinter.
'''
import tkinter as tk
from tkinter import messagebox
from connect_four_game import ConnectFourGame
class ConnectFourGUI:
    def __init__(self):
        self.game = ConnectFourGame()
        self.window = tk.Tk()
        self.window.title("Connect Four")
        self.create_board()
    def create_board(self):
        self.buttons = []
        for col in range(self.game.COLUMNS):
            button = tk.Button(self.window, text=str(col+1), command=lambda c=col: self.handle_click(c))
            button.grid(row=0, column=col)
            self.buttons.append(button)
        self.labels = [[None for _ in range(self.game.COLUMNS)] for _ in range(self.game.ROWS)]
        for row in range(self.game.ROWS):
            for col in range(self.game.COLUMNS):
                label = tk.Label(self.window, text=' ', width=4, height=2, borderwidth=2, relief="groove")
                label.grid(row=row+1, column=col)
                self.labels[row][col] = label
    def update_board(self):
        for row in range(self.game.ROWS):
            for col in range(self.game.COLUMNS):
                self.labels[row][col]['text'] = self.game.board[row][col]
    def handle_click(self, column):
        position = self.game.drop_disc(column)
        if position:
            row, col = position
            self.update_board()
            if self.game.check_winner(row, col):
                self.show_message(f"{self.game.current_player} wins!")
            elif self.game.is_draw():
                self.show_message("It's a draw!")
            else:
                self.game.switch_player()
    def show_message(self, message):
        response = messagebox.askquestion("Game Over", f"{message}\nDo you want to play again?")
        if response == 'yes':
            self.reset_game()
        else:
            self.window.quit()
    def reset_game(self):
        self.game = ConnectFourGame()
        self.update_board()
    def run(self):
        self.window.mainloop()