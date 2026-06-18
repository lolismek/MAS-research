'''
Tkinter-based GUI for playing Gomoku on a 15x15 board.
If Tkinter is unavailable in the environment, this module provides a safe fallback.
'''
try:
    import tkinter as tk
    from tkinter import messagebox
    TK_AVAILABLE = True
except ModuleNotFoundError:
    tk = None
    messagebox = None
    TK_AVAILABLE = False
from gomoku_game import GomokuGame, EMPTY, BLACK, WHITE
class GomokuGUI:
    """Graphical user interface for the Gomoku game."""
    def __init__(self) -> None:
        self.game = GomokuGame()
        self.last_move_highlight = True
        self.status_var = None
        if not TK_AVAILABLE:
            raise RuntimeError(
                "Tkinter is not available in this Python environment. "
                "Use the CLI version via main.py."
            )
        self.root = tk.Tk()
        self.root.title("Gomoku")
        self.root.resizable(False, False)
        # Explicit, symmetric board geometry:
        # 15 intersections => 14 gaps between first and last intersection.
        self.cell_size = 36
        self.margin = 24
        self.board_span = self.cell_size * (self.game.board_size - 1)
        self.board_pixel_size = self.margin * 2 + self.board_span
        self.status_var = tk.StringVar()
        self._build_ui()
        self._update_status()
    def _build_ui(self) -> None:
        """Create widgets and layout."""
        top_frame = tk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        status_label = tk.Label(top_frame, textvariable=self.status_var, font=("Arial", 12, "bold"))
        status_label.pack(side=tk.LEFT)
        reset_button = tk.Button(top_frame, text="New Game", command=self.reset_game)
        reset_button.pack(side=tk.RIGHT)
        self.canvas = tk.Canvas(
            self.root,
            width=self.board_pixel_size,
            height=self.board_pixel_size,
            bg="#DDB77B",
            highlightthickness=0,
        )
        self.canvas.pack(padx=10, pady=(0, 10))
        self.canvas.bind("<Button-1>", self.on_click)
        self._draw_board()
    def _draw_board(self) -> None:
        """Draw the board grid, playable frame, star points, and stones."""
        self.canvas.delete("all")
        left = self.margin
        top = self.margin
        right = self.margin + self.board_span
        bottom = self.margin + self.board_span
        self.canvas.create_rectangle(left, top, right, bottom, outline="#6B4F2A", width=2)
        for i in range(self.game.board_size):
            x = self.margin + i * self.cell_size
            self.canvas.create_line(x, top, x, bottom, fill="black")
            y = self.margin + i * self.cell_size
            self.canvas.create_line(left, y, right, y, fill="black")
        for row, col in [
            (3, 3), (3, 7), (3, 11),
            (7, 3), (7, 7), (7, 11),
            (11, 3), (11, 7), (11, 11),
        ]:
            x, y = self._grid_to_pixel(row, col)
            r = 3
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill="black", outline="black")
        for row in range(self.game.board_size):
            for col in range(self.game.board_size):
                cell = self.game.board[row][col]
                if cell != EMPTY:
                    self._draw_stone(row, col, cell)
        if self.last_move_highlight and self.game.last_move is not None:
            row, col = self.game.last_move
            self._draw_last_move_highlight(row, col)
    def _draw_last_move_highlight(self, row: int, col: int) -> None:
        """Draw a small ring around the last placed stone."""
        x, y = self._grid_to_pixel(row, col)
        radius = self.cell_size // 2 - 1
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline="#E53935",
            width=2,
        )
    def _draw_stone(self, row: int, col: int, player: int) -> None:
        """Draw a stone at the given board intersection."""
        x, y = self._grid_to_pixel(row, col)
        radius = self.cell_size // 2 - 3
        if player == BLACK:
            fill = "black"
            outline = "#222222"
        else:
            fill = "white"
            outline = "#888888"
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=1,
        )
    def _grid_to_pixel(self, row: int, col: int) -> tuple[int, int]:
        """Convert board coordinates to canvas pixel coordinates."""
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        return x, y
    def _pixel_to_grid(self, x: int, y: int) -> tuple[int, int] | None:
        """
        Convert canvas pixel coordinates to the nearest board intersection.
        """
        col = round((x - self.margin) / self.cell_size)
        row = round((y - self.margin) / self.cell_size)
        if not (0 <= row < self.game.board_size and 0 <= col < self.game.board_size):
            return None
        gx, gy = self._grid_to_pixel(row, col)
        tolerance = self.cell_size * 0.35
        if abs(x - gx) <= tolerance and abs(y - gy) <= tolerance:
            return row, col
        return None
    def on_click(self, event: "tk.Event") -> None:
        """Handle mouse clicks on the board."""
        if self.game.winner is not None or self.game.is_draw():
            return
        grid_pos = self._pixel_to_grid(event.x, event.y)
        if grid_pos is None:
            return
        row, col = grid_pos
        if self.game.make_move(row, col):
            self._draw_board()
            self._update_status()
            if self.game.winner is not None:
                winner_text = "Black" if self.game.winner == BLACK else "White"
                messagebox.showinfo("Game Over", f"{winner_text} wins!")
            elif self.game.is_draw():
                messagebox.showinfo("Game Over", "The game is a draw.")
    def _update_status(self) -> None:
        """Update the status bar text."""
        if self.game.winner == BLACK:
            text = "Black wins!"
        elif self.game.winner == WHITE:
            text = "White wins!"
        elif self.game.is_draw():
            text = "Draw game."
        else:
            text = f"Current player: {'Black' if self.game.current_player == BLACK else 'White'}"
        self.status_var.set(text)
    def reset_game(self) -> None:
        """Start a new game."""
        self.game.reset()
        self._draw_board()
        self._update_status()
    def run(self) -> None:
        """Launch the GUI application."""
        self.root.mainloop()