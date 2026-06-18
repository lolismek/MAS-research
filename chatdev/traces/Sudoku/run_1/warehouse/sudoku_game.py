'''
Contains the SudokuGame GUI class which manages:
- puzzle display
- user input
- validation
- completion detection
- restart/new game functionality
'''
import tkinter as tk
from tkinter import messagebox
from sudoku_utils import (
    board_is_complete,
    generate_puzzle,
    is_board_valid,
    is_valid_move,
)
class SudokuGame:
    '''GUI controller for a classic Sudoku game.'''
    def __init__(self, master):
        self.master = master
        self.puzzle, self.solution = generate_puzzle(empty_cells=45)
        self.entries = [[None for _ in range(9)] for _ in range(9)]
        self.status_var = tk.StringVar()
        self.status_var.set("Fill the grid. Red cells indicate mistakes.")
        self._build_ui()
        self._load_board()
    def _build_ui(self):
        '''Create the full interface.'''
        outer = tk.Frame(self.master, padx=10, pady=10)
        outer.pack()
        title = tk.Label(
            outer,
            text="Sudoku",
            font=("Arial", 20, "bold")
        )
        title.grid(row=0, column=0, columnspan=9, pady=(0, 10))
        board_frame = tk.Frame(outer, bd=2, relief=tk.SOLID)
        board_frame.grid(row=1, column=0, columnspan=9)
        vcmd = (self.master.register(self._validate_entry), "%P")
        for r in range(9):
            for c in range(9):
                pad_x = (0, 2)
                pad_y = (0, 2)
                if c in (2, 5):
                    pad_x = (0, 8)
                if r in (2, 5):
                    pad_y = (0, 8)
                entry = tk.Entry(
                    board_frame,
                    width=2,
                    font=("Arial", 18),
                    justify="center",
                    validate="key",
                    validatecommand=vcmd
                )
                entry.grid(row=r, column=c, padx=pad_x, pady=pad_y, ipady=6)
                entry.bind("<FocusOut>", lambda e, row=r, col=c: self._check_cell(row, col))
                entry.bind("<KeyRelease>", lambda e, row=r, col=c: self._check_cell(row, col))
                self.entries[r][c] = entry
        button_frame = tk.Frame(outer, pady=10)
        button_frame.grid(row=2, column=0, columnspan=9)
        tk.Button(button_frame, text="Check Puzzle", command=self.check_puzzle, width=14).grid(
            row=0, column=0, padx=5
        )
        tk.Button(button_frame, text="New Game", command=self.new_game, width=14).grid(
            row=0, column=1, padx=5
        )
        tk.Button(button_frame, text="Reveal Solution", command=self.reveal_solution, width=14).grid(
            row=0, column=2, padx=5
        )
        status = tk.Label(
            outer,
            textvariable=self.status_var,
            font=("Arial", 11),
            fg="blue",
            wraplength=420,
            justify="left"
        )
        status.grid(row=3, column=0, columnspan=9, sticky="w")
    def _validate_entry(self, proposed):
        '''Allow only empty string or a single digit 1-9.'''
        return proposed == "" or (len(proposed) == 1 and proposed in "123456789")
    def _load_board(self):
        '''Load the current puzzle into the GUI.'''
        for r in range(9):
            for c in range(9):
                entry = self.entries[r][c]
                entry.config(state="normal", disabledforeground="black")
                entry.delete(0, tk.END)
                entry.config(bg="white")
                if self.puzzle[r][c] != 0:
                    entry.insert(0, str(self.puzzle[r][c]))
                    entry.config(
                        state="disabled",
                        disabledforeground="black",
                        disabledbackground="#e6e6e6"
                    )
        self.status_var.set("Fill the grid. Red cells indicate mistakes.")
    def _get_board_from_entries(self):
        '''Read the current board state from the GUI.'''
        board = [[0 for _ in range(9)] for _ in range(9)]
        for r in range(9):
            for c in range(9):
                value = self.entries[r][c].get().strip()
                board[r][c] = int(value) if value else 0
        return board
    def _check_cell(self, row, col):
        '''Validate a single cell against Sudoku rules.'''
        entry = self.entries[row][col]
        if entry.cget("state") == "disabled":
            return
        value = entry.get().strip()
        if not value:
            entry.config(bg="white")
            return
        try:
            num = int(value)
        except ValueError:
            entry.config(bg="#ffd9d9")
            return
        current_board = self._get_board_from_entries()
        if current_board[row][col] == 0:
            entry.config(bg="white")
            return
        if is_valid_move(current_board, row, col, num):
            entry.config(bg="#d9ffd9")
        else:
            entry.config(bg="#ffd9d9")
    def check_puzzle(self):
        '''Check the entire puzzle for mistakes and completion.'''
        current_board = self._get_board_from_entries()
        errors = []
        for r in range(9):
            for c in range(9):
                if self.puzzle[r][c] != 0:
                    continue
                value = current_board[r][c]
                entry = self.entries[r][c]
                if value == 0:
                    entry.config(bg="white")
                    continue
                if not (1 <= value <= 9):
                    entry.config(bg="#ffd9d9")
                    errors.append((r + 1, c + 1))
                    continue
                temp_board = [row[:] for row in current_board]
                temp_board[r][c] = 0
                valid = is_valid_move(temp_board, r, c, value)
                if valid:
                    entry.config(bg="#d9ffd9")
                else:
                    entry.config(bg="#ffd9d9")
                    errors.append((r + 1, c + 1))
        if errors:
            self.status_var.set(
                f"There are mistakes in the puzzle. First issue at row {errors[0][0]}, column {errors[0][1]}."
            )
            return
        if board_is_complete(current_board):
            if is_board_valid(current_board):
                self.status_var.set("Congratulations! You completed the Sudoku puzzle.")
                messagebox.showinfo("Sudoku", "Congratulations! You completed the Sudoku puzzle.")
            else:
                self.status_var.set("The board is complete but invalid. Please review your entries.")
                messagebox.showwarning("Sudoku", "The board is complete but invalid. Please review your entries.")
        else:
            self.status_var.set("So far so good. Keep going!")
    def reveal_solution(self):
        '''Show the completed solution in the grid.'''
        for r in range(9):
            for c in range(9):
                entry = self.entries[r][c]
                entry.config(state="normal")
                entry.delete(0, tk.END)
                entry.insert(0, str(self.solution[r][c]))
                if self.puzzle[r][c] != 0:
                    entry.config(
                        state="disabled",
                        disabledforeground="black",
                        disabledbackground="#e6e6e6"
                    )
                else:
                    entry.config(bg="#e0f0ff")
        self.status_var.set("Solution revealed.")
    def new_game(self):
        '''Generate a fresh puzzle and reload the board.'''
        self.puzzle, self.solution = generate_puzzle(empty_cells=45)
        self._load_board()