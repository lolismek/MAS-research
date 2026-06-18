"""
Tkinter GUI for a Strands-like puzzle game.
"""
import tkinter as tk
from tkinter import messagebox
from game import StrandsGame
from puzzles import get_puzzle_names
class StrandsApp:
    """Graphical application for playing a Strands-like game."""
    CELL_SIZE = 72
    PAD = 18
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Strands Puzzle")
        self.root.resizable(False, False)
        self.selected_cells = []
        self.current_line_ids = []
        self.cell_rect_ids = {}
        self.cell_text_ids = {}
        self.cell_coords = {}
        try:
            self.game = StrandsGame()
        except Exception as exc:
            messagebox.showerror("Startup Error", f"Unable to load puzzle data:\n{exc}")
            raise
        self._build_ui()
        self._load_game()
    def _build_ui(self) -> None:
        """Create all GUI widgets."""
        top = tk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)
        self.theme_label = tk.Label(top, text="", font=("Arial", 13, "bold"))
        self.theme_label.pack(side=tk.LEFT)
        controls = tk.Frame(self.root)
        controls.pack(side=tk.TOP, fill=tk.X, padx=10)
        self.puzzle_var = tk.StringVar(value=self.game.puzzle_name)
        puzzle_menu = tk.OptionMenu(
            controls, self.puzzle_var, *get_puzzle_names(), command=self._switch_puzzle
        )
        puzzle_menu.config(width=18)
        puzzle_menu.pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(controls, text="New Game", command=self._new_game).pack(side=tk.LEFT, padx=4)
        tk.Button(controls, text="Clear", command=self._clear_selection).pack(side=tk.LEFT, padx=4)
        tk.Button(controls, text="Undo", command=self._undo_last).pack(side=tk.LEFT, padx=4)
        tk.Button(controls, text="Hint", command=self._use_hint).pack(side=tk.LEFT, padx=4)
        stats = tk.Frame(self.root)
        stats.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(6, 0))
        self.status_label = tk.Label(stats, text="", font=("Arial", 11))
        self.status_label.pack(side=tk.LEFT)
        self.hint_label = tk.Label(stats, text="", font=("Arial", 11))
        self.hint_label.pack(side=tk.RIGHT)
        board_frame = tk.Frame(self.root, bg="#222")
        board_frame.pack(side=tk.TOP, padx=10, pady=10)
        width = self.game.cols * self.CELL_SIZE
        height = self.game.rows * self.CELL_SIZE
        self.canvas = tk.Canvas(
            board_frame, width=width, height=height, bg="#111", highlightthickness=0
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self._draw_board()
    def run(self) -> None:
        """Start the Tk event loop."""
        self.root.mainloop()
    def _load_game(self) -> None:
        """Load board and refresh the display."""
        self.game.reset()
        self.selected_cells.clear()
        self.current_line_ids.clear()
        self._draw_board()
        self._refresh_ui()
    def _switch_puzzle(self, puzzle_name: str) -> None:
        """Switch to another puzzle by name."""
        try:
            self.game.load_puzzle(puzzle_name)
            self._load_game()
        except Exception as exc:
            messagebox.showerror("Puzzle Error", f"Could not load puzzle:\n{exc}")
    def _new_game(self) -> None:
        """Restart the current puzzle."""
        self._load_game()
    def _clear_selection(self) -> None:
        """Clear the currently selected path."""
        self.selected_cells.clear()
        self._remove_temp_line()
        self._refresh_selection_visuals()
        self._refresh_ui()
    def _undo_last(self) -> None:
        """Remove the last found word if possible."""
        if self.game.undo_last_word():
            self.selected_cells.clear()
            self._remove_temp_line()
            self._draw_board()
            self._refresh_ui()
        else:
            messagebox.showinfo("Undo", "Nothing to undo.")
    def _use_hint(self) -> None:
        """Reveal a hint if one is available."""
        hint = self.game.get_hint()
        if hint:
            messagebox.showinfo("Hint", hint)
            self._refresh_ui()
        else:
            messagebox.showinfo(
                "Hint", "No hints available yet. Find 3 non-theme words to unlock one."
            )
    def _on_click(self, event) -> None:
        """Handle mouse click to start or extend selection."""
        cell = self._cell_from_xy(event.x, event.y)
        if cell is None:
            return
        if not self.selected_cells:
            self.selected_cells = [cell]
            self._refresh_selection_visuals()
            self._draw_temp_line()
            return
        if cell == self.selected_cells[-1]:
            return
        if self.game.is_adjacent(self.selected_cells[-1], cell) and cell not in self.selected_cells:
            self.selected_cells.append(cell)
            self._refresh_selection_visuals()
            self._draw_temp_line()
    def _on_drag(self, event) -> None:
        """Handle dragging over cells to extend selection."""
        cell = self._cell_from_xy(event.x, event.y)
        if cell is None or not self.selected_cells:
            return
        if cell == self.selected_cells[-1]:
            return
        if self.game.is_adjacent(self.selected_cells[-1], cell) and cell not in self.selected_cells:
            self.selected_cells.append(cell)
            self._refresh_selection_visuals()
            self._draw_temp_line()
    def _on_release(self, event) -> None:
        """Finalize the selected word when mouse button is released."""
        if len(self.selected_cells) < 2:
            self.selected_cells.clear()
            self._remove_temp_line()
            self._refresh_selection_visuals()
            return
        word = self.game.word_from_path(self.selected_cells)
        result = self.game.submit_attempt(word, self.selected_cells)
        if result["found"]:
            self._draw_board()
            if self.game.is_complete():
                messagebox.showinfo(
                    "Completed",
                    "Puzzle completed! You filled the board and found all theme words.",
                )
        else:
            if result["reason"] == "invalid":
                messagebox.showwarning(
                    "Invalid", "That path does not form a valid word in the board."
                )
            elif result["reason"] == "duplicate":
                messagebox.showinfo("Already Found", "That word has already been found.")
            else:
                self.game.record_non_theme_word(word)
                if self.game.hints_available() > 0:
                    self._refresh_ui()
                    if self.game.hints_available() == 1:
                        messagebox.showinfo("Hint Unlocked", "You unlocked a hint!")
                else:
                    self._refresh_ui()
        self.selected_cells.clear()
        self._remove_temp_line()
        self._refresh_selection_visuals()
        self._refresh_ui()
    def _draw_board(self) -> None:
        """Render the board with current highlights."""
        self.canvas.delete("all")
        self.cell_rect_ids.clear()
        self.cell_text_ids.clear()
        self.cell_coords.clear()
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                x1 = c * self.CELL_SIZE
                y1 = r * self.CELL_SIZE
                x2 = x1 + self.CELL_SIZE
                y2 = y1 + self.CELL_SIZE
                letter = self.game.board[r][c]
                key = (r, c)
                self.cell_coords[key] = ((x1 + x2) / 2, (y1 + y2) / 2)
                fill = "#1c1c1c"
                outline = "#444"
                if key in self.game.spangram_cells:
                    fill = "#ffe66d"
                    outline = "#c9a400"
                elif key in self.game.found_theme_cells:
                    fill = "#7fb3ff"
                    outline = "#2c6ccf"
                rect_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=fill, outline=outline, width=2
                )
                text_id = self.canvas.create_text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2,
                    text=letter,
                    fill="#ffffff",
                    font=("Arial", 22, "bold"),
                )
                self.cell_rect_ids[key] = rect_id
                self.cell_text_ids[key] = text_id
        self._refresh_selection_visuals()
        self._refresh_ui()
    def _refresh_selection_visuals(self) -> None:
        """Highlight selected cells and update their appearance."""
        for key, rect_id in self.cell_rect_ids.items():
            if key in self.selected_cells:
                self.canvas.itemconfigure(rect_id, outline="#ffffff", width=4)
            else:
                if key in self.game.spangram_cells:
                    self.canvas.itemconfigure(rect_id, outline="#c9a400", width=2)
                elif key in self.game.found_theme_cells:
                    self.canvas.itemconfigure(rect_id, outline="#2c6ccf", width=2)
                else:
                    self.canvas.itemconfigure(rect_id, outline="#444", width=2)
    def _draw_temp_line(self) -> None:
        """Draw line between current selection cells."""
        self._remove_temp_line()
        if len(self.selected_cells) < 2:
            return
        points = []
        for cell in self.selected_cells:
            points.extend(self.cell_coords[cell])
        self.current_line_ids.append(
            self.canvas.create_line(*points, fill="#ffffff", width=5, smooth=True, splinesteps=12)
        )
    def _remove_temp_line(self) -> None:
        """Remove temporary selection line."""
        for item in self.current_line_ids:
            self.canvas.delete(item)
        self.current_line_ids.clear()
    def _refresh_ui(self) -> None:
        """Refresh text labels and title state."""
        self.theme_label.config(text=f"Theme: {self.game.theme}")
        self.status_label.config(
            text=(
                f"Found theme words: {len(self.game.found_theme_words)}/{len(self.game.theme_words)}   "
                f"Non-theme words: {len(self.game.non_theme_words)}"
            )
        )
        self.hint_label.config(
            text=(
                f"Hints available: {self.game.hints_available()}   "
                f"Board complete: {'Yes' if self.game.is_complete() else 'No'}"
            )
        )
    def _cell_from_xy(self, x: int, y: int):
        """Convert canvas coordinates into a board cell."""
        col = x // self.CELL_SIZE
        row = y // self.CELL_SIZE
        if 0 <= row < self.game.rows and 0 <= col < self.game.cols:
            return (row, col)
        return None