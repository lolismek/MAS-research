'''
This is the main file for the Tic-Tac-Toe game application. It initializes the game and GUI.
'''
import tkinter as tk
from tkinter import messagebox
class TicTacToeGame:
    '''
    This class manages the game logic for Tic-Tac-Toe, including the board state, current player, and winner determination.
    '''
    def __init__(self):
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.winner = None
    def reset_game(self):
        '''
        Resets the game to its initial state.
        '''
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.winner = None
    def make_move(self, row, col):
        '''
        Attempts to make a move on the board at the specified row and column.
        Returns True if the move is successful, otherwise False.
        '''
        if self.board[row][col] == '' and self.winner is None:
            self.board[row][col] = self.current_player
            if self.check_winner():
                self.winner = self.current_player
            else:
                self.switch_player()
            return True
        return False
    def check_winner(self):
        '''
        Checks the board for a winner or a draw.
        Returns True if the game is over, otherwise False.
        '''
        # Check rows, columns, and diagonals for a win
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != '':
                return True
            if self.board[0][i] == self.board[1][i] == self.board[2][i] != '':
                return True
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != '':
            return True
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != '':
            return True
        # Check for draw
        if all(self.board[row][col] != '' for row in range(3) for col in range(3)):
            self.winner = 'Draw'
            return True
        return False
    def switch_player(self):
        '''
        Switches the current player from X to O or from O to X.
        '''
        self.current_player = 'O' if self.current_player == 'X' else 'X'
class TicTacToeGUI:
    '''
    This class manages the graphical user interface for the Tic-Tac-Toe game.
    '''
    def __init__(self, root, game):
        self.root = root
        self.game = game
        self.buttons = [[None for _ in range(3)] for _ in range(3)]
        self.setup_ui()
    def setup_ui(self):
        '''
        Sets up the user interface for the Tic-Tac-Toe game.
        '''
        self.root.title("Tic-Tac-Toe")
        for row in range(3):
            for col in range(3):
                button = tk.Button(self.root, text='', font=('Arial', 24), width=5, height=2,
                                   command=lambda r=row, c=col: self.on_button_click(r, c))
                button.grid(row=row, column=col)
                self.buttons[row][col] = button
    def on_button_click(self, row, col):
        '''
        Handles button click events, making a move and updating the UI.
        '''
        if self.game.make_move(row, col):
            self.update_button_text(row, col)
            if self.game.winner:
                self.show_winner(self.game.winner)
    def update_button_text(self, row, col):
        '''
        Updates the text on a button to reflect the current state of the board.
        '''
        self.buttons[row][col].config(text=self.game.board[row][col])
    def show_winner(self, winner):
        '''
        Displays a message box showing the winner or if the game is a draw, then resets the game.
        '''
        if winner == 'Draw':
            messagebox.showinfo("Game Over", "It's a draw!")
        else:
            messagebox.showinfo("Game Over", f"Player {winner} wins!")
        self.reset_buttons()
        self.game.reset_game()
    def reset_buttons(self):
        '''
        Resets all buttons to their initial state.
        '''
        for row in range(3):
            for col in range(3):
                self.buttons[row][col].config(text='')
if __name__ == "__main__":
    root = tk.Tk()
    game = TicTacToeGame()
    gui = TicTacToeGUI(root, game)
    root.mainloop()