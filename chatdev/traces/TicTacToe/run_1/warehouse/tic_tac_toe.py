'''
Tic-Tac-Toe game implemented with a user-friendly GUI.
Features:
- 3x3 board
- two-player alternating turns
- winner detection
- draw detection
- restart capability
- move tracking for both players
- robust fallback to console mode when Tkinter is unavailable
'''
# Tkinter may not be available in some Python environments (e.g. missing _tkinter).
# To make the application execute smoothly and robustly, we provide a graceful
# console fallback instead of crashing at import time.
try:
    import tkinter as tk
    from tkinter import messagebox
    TK_AVAILABLE = True
except Exception:
    tk = None
    messagebox = None
    TK_AVAILABLE = False
class TicTacToeGame:
    '''
    Encapsulates the Tic-Tac-Toe game state and rules.
    '''
    def __init__(self):
        self.reset_game()
    def reset_game(self):
        '''
        Reset the board and game state.
        '''
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.current_player = "X"
        self.winner = None
        self.moves = {"X": 0, "O": 0}
        self.game_over = False
    def make_move(self, row, col):
        '''
        Place the current player's mark on the board if the move is valid.
        Returns True if the move was made, otherwise False.
        '''
        if self.game_over:
            return False
        if self.board[row][col] != "":
            return False
        self.board[row][col] = self.current_player
        self.moves[self.current_player] += 1
        if self.check_winner():
            self.winner = self.current_player
            self.game_over = True
        elif self.is_draw():
            self.game_over = True
        else:
            self.current_player = "O" if self.current_player == "X" else "X"
        return True
    def check_winner(self):
        '''
        Check all winning combinations.
        Returns True if the current player has won.
        '''
        p = self.current_player
        b = self.board
        for r in range(3):
            if b[r][0] == b[r][1] == b[r][2] == p:
                return True
        for c in range(3):
            if b[0][c] == b[1][c] == b[2][c] == p:
                return True
        if b[0][0] == b[1][1] == b[2][2] == p:
            return True
        if b[0][2] == b[1][1] == b[2][0] == p:
            return True
        return False
    def is_draw(self):
        '''
        Return True if the board is full and there is no winner.
        '''
        for row in self.board:
            for cell in row:
                if cell == "":
                    return False
        return self.winner is None
class TicTacToeApp:
    '''
    Tkinter GUI application for Tic-Tac-Toe.
    '''
    def __init__(self, root):
        self.root = root
        self.root.title("Tic-Tac-Toe")
        self.root.resizable(False, False)
        self.game = TicTacToeGame()
        self.status_var = tk.StringVar()
        self.moves_var = tk.StringVar()
        self._build_ui()
        self._refresh_ui()
    def _build_ui(self):
        '''
        Create the GUI widgets.
        '''
        container = tk.Frame(self.root, padx=15, pady=15)
        container.pack()
        title = tk.Label(
            container,
            text="Tic-Tac-Toe",
            font=("Arial", 20, "bold")
        )
        title.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        status_label = tk.Label(
            container,
            textvariable=self.status_var,
            font=("Arial", 12),
            fg="blue"
        )
        status_label.grid(row=1, column=0, columnspan=3, pady=(0, 6))
        moves_label = tk.Label(
            container,
            textvariable=self.moves_var,
            font=("Arial", 10)
        )
        moves_label.grid(row=2, column=0, columnspan=3, pady=(0, 12))
        self.buttons = []
        board_frame = tk.Frame(container)
        board_frame.grid(row=3, column=0, columnspan=3)
        for r in range(3):
            row_buttons = []
            for c in range(3):
                btn = tk.Button(
                    board_frame,
                    text="",
                    font=("Arial", 24, "bold"),
                    width=4,
                    height=2,
                    command=lambda row=r, col=c: self.on_cell_click(row, col)
                )
                btn.grid(row=r, column=c, padx=3, pady=3)
                row_buttons.append(btn)
            self.buttons.append(row_buttons)
        restart_btn = tk.Button(
            container,
            text="Restart Game",
            font=("Arial", 12),
            command=self.restart_game
        )
        restart_btn.grid(row=4, column=0, columnspan=3, pady=(12, 0))
    def on_cell_click(self, row, col):
        '''
        Handle a user clicking a cell.
        '''
        moved = self.game.make_move(row, col)
        if not moved:
            return
        self._refresh_ui()
        if self.game.winner:
            messagebox.showinfo("Game Over", f"Player {self.game.winner} wins!")
        elif self.game.game_over and self.game.winner is None:
            messagebox.showinfo("Game Over", "It's a draw!")
    def restart_game(self):
        '''
        Restart the game from scratch.
        '''
        self.game.reset_game()
        self._refresh_ui()
    def _refresh_ui(self):
        '''
        Update buttons and status labels to reflect current game state.
        '''
        for r in range(3):
            for c in range(3):
                value = self.game.board[r][c]
                btn = self.buttons[r][c]
                btn.config(text=value)
                if value != "" or self.game.game_over:
                    btn.config(state=tk.DISABLED)
                else:
                    btn.config(state=tk.NORMAL)
        if self.game.winner:
            self.status_var.set(f"Winner: Player {self.game.winner}")
        elif self.game.game_over:
            self.status_var.set("Game ended in a draw.")
        else:
            self.status_var.set(f"Current turn: Player {self.game.current_player}")
        self.moves_var.set(
            f"Moves - X: {self.game.moves['X']} | O: {self.game.moves['O']}"
        )
def _console_fallback():
    '''
    Console fallback for environments where Tkinter is unavailable.
    This keeps the program runnable and testable instead of failing on import.
    '''
    print("Tkinter is not available in this Python environment.")
    print("Running Tic-Tac-Toe in console mode.")
    game = TicTacToeGame()
    def print_board():
        symbols = []
        for row in game.board:
            symbols.append(" | ".join(cell if cell else " " for cell in row))
        print("\n-----")
        for i, row in enumerate(symbols):
            print(row)
            if i < 2:
                print("---------")
        print("-----\n")
    while not game.game_over:
        print_board()
        print(f"Current turn: Player {game.current_player}")
        print(f"Moves - X: {game.moves['X']} | O: {game.moves['O']}")
        try:
            raw = input("Enter move as row,col (0-2,0-2): ").strip()
            row_str, col_str = raw.split(",")
            row, col = int(row_str), int(col_str)
            if not (0 <= row <= 2 and 0 <= col <= 2):
                print("Invalid input. Please use values from 0 to 2.")
                continue
        except Exception:
            print("Invalid input format. Example: 1,2")
            continue
        if not game.make_move(row, col):
            print("Cell already occupied or move invalid. Try again.")
    print_board()
    if game.winner:
        print(f"Game Over: Player {game.winner} wins!")
    else:
        print("Game Over: It's a draw!")
def main():
    '''
    Launch the Tic-Tac-Toe application.
    '''
    if TK_AVAILABLE:
        try:
            root = tk.Tk()
            app = TicTacToeApp(root)
            root.mainloop()
            return
        except Exception:
            # If Tkinter is installed but cannot create a window (e.g. headless env),
            # fall back to console mode.
            pass
    _console_fallback()