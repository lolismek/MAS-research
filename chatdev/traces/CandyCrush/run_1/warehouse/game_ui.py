'''
Tkinter-based user interface for the Match-3 puzzle game.
'''
from __future__ import annotations
from typing import TYPE_CHECKING, Dict
if TYPE_CHECKING:
    from game_controller import GameController
try:
    import tkinter as tk
    _TK_IMPORT_ERROR = None
except Exception as exc:  # Handles missing _tkinter module gracefully.
    tk = None  # type: ignore[assignment]
    _TK_IMPORT_ERROR = exc
class _FallbackStringVar:
    """Simple StringVar-like replacement for environments without Tk support."""
    def __init__(self, value: str = "") -> None:
        self._value = value
    def set(self, value: str) -> None:
        self._value = value
    def get(self) -> str:
        return self._value
class _FallbackCanvas:
    def __init__(self) -> None:
        self._overlay_id = None
    def delete(self, *_args, **_kwargs) -> None:
        return
    def create_rectangle(self, *_args, **_kwargs) -> int:
        return 1
    def create_text(self, *_args, **_kwargs) -> int:
        return 1
    def create_line(self, *_args, **_kwargs) -> int:
        return 1
    def bind(self, *_args, **_kwargs) -> None:
        return
class _FallbackWindow:
    def title(self, *_args, **_kwargs) -> None:
        return
    def resizable(self, *_args, **_kwargs) -> None:
        return
    def mainloop(self) -> None:
        print("Tkinter is unavailable in this environment. Game UI cannot be displayed.")
class GameUI:
    """Graphical user interface for rendering the board and handling user input."""
    def __init__(
        self,
        controller: "GameController",
        rows: int,
        cols: int,
        cell_size: int,
        target_score: int,
    ) -> None:
        self.controller = controller
        self.rows = rows
        self.cols = cols
        self.cell_size = cell_size
        self.target_score = target_score
        self._game_over_overlay = None
        if tk is not None:
            try:
                self.window = tk.Tk()
                self.window.title("Match-3 Puzzle Game")
                self.window.resizable(False, False)
                string_var = tk.StringVar
                frame_cls = tk.Frame
                label_cls = tk.Label
                canvas_cls = tk.Canvas
                self._tk_available = True
            except Exception:
                self.window = _FallbackWindow()
                string_var = _FallbackStringVar
                frame_cls = None
                label_cls = None
                canvas_cls = None
                self._tk_available = False
        else:
            self.window = _FallbackWindow()
            string_var = _FallbackStringVar
            frame_cls = None
            label_cls = None
            canvas_cls = None
            self._tk_available = False
        self.colors: Dict[int, str] = {
            0: "#ffffff",
            1: "#ff6b6b",
            2: "#ffd93d",
            3: "#6bcb77",
            4: "#4d96ff",
            5: "#b983ff",
            6: "#ff9f1c",
            7: "#00c2a8",
            8: "#ff66c4",
        }
        self.canvas_width = self.cols * self.cell_size
        self.canvas_height = self.rows * self.cell_size
        self.score_var = string_var(value="Score: 0")
        self.moves_var = string_var(value="Moves Left: 0")
        self.target_var = string_var(value=f"Target: {self.target_score}")
        self.status_var = string_var(value="")
        if self._tk_available:
            self.hud_frame = frame_cls(self.window, padx=10, pady=10)
            self.hud_frame.pack(fill=tk.X)
            self.score_label = label_cls(self.hud_frame, textvariable=self.score_var, font=("Arial", 12, "bold"))
            self.moves_label = label_cls(self.hud_frame, textvariable=self.moves_var, font=("Arial", 12, "bold"))
            self.target_label = label_cls(self.hud_frame, textvariable=self.target_var, font=("Arial", 12, "bold"))
            self.score_label.grid(row=0, column=0, padx=8)
            self.moves_label.grid(row=0, column=1, padx=8)
            self.target_label.grid(row=0, column=2, padx=8)
            self.status_label = label_cls(self.window, textvariable=self.status_var, anchor="w", padx=10)
            self.status_label.pack(fill=tk.X)
            self.canvas = canvas_cls(
                self.window,
                width=self.canvas_width,
                height=self.canvas_height,
                bg="#f5f5f5",
                highlightthickness=0,
            )
            self.canvas.pack(padx=10, pady=10)
            self.canvas.bind("<Button-1>", self._on_canvas_click)
        else:
            self.canvas = _FallbackCanvas()
    def run(self) -> None:
        """Start the Tkinter event loop."""
        self.window.mainloop()
    def set_status(self, message: str) -> None:
        """Update the status message shown below the HUD."""
        self.status_var.set(message)
    def update_hud(self, score: int, moves_left: int) -> None:
        """Update score and moves labels."""
        self.score_var.set(f"Score: {score}")
        self.moves_var.set(f"Moves Left: {moves_left}")
    def clear_game_over_overlay(self) -> None:
        """Remove any existing game-over overlay from the canvas."""
        if self._game_over_overlay is not None:
            self.canvas.delete(self._game_over_overlay)
            self._game_over_overlay = None
    def render(self) -> None:
        """Redraw the entire board."""
        if not self._tk_available:
            return
        self.canvas.delete("all")
        board = self.controller.board.grid
        selected = self.controller.selected
        for r in range(self.rows):
            for c in range(self.cols):
                x1 = c * self.cell_size
                y1 = r * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                candy = board[r][c]
                fill = self.colors.get(candy, "#cccccc")
                outline = "#333333"
                width = 1
                if selected == (r, c):
                    outline = "#000000"
                    width = 4
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width)
                if candy != 0:
                    pad = 10
                    self.canvas.create_oval(
                        x1 + pad,
                        y1 + pad,
                        x2 - pad,
                        y2 - pad,
                        fill=fill,
                        outline="#ffffff",
                        width=2,
                    )
        for r in range(self.rows + 1):
            y = r * self.cell_size
            self.canvas.create_line(0, y, self.canvas_width, y, fill="#dddddd")
        for c in range(self.cols + 1):
            x = c * self.cell_size
            self.canvas.create_line(x, 0, x, self.canvas_height, fill="#dddddd")
    def show_game_over(self, message: str) -> None:
        """Display a game-over overlay with the final message."""
        if not self._tk_available:
            print(f"Game Over: {message}")
            return
        self.clear_game_over_overlay()
        self._game_over_overlay = self.canvas.create_rectangle(
            20,
            self.canvas_height // 2 - 50,
            self.canvas_width - 20,
            self.canvas_height // 2 + 50,
            fill="#000000",
            stipple="gray50",
            outline="#ffffff",
            width=2,
        )
        self.canvas.create_text(
            self.canvas_width // 2,
            self.canvas_height // 2 - 10,
            text="Game Over",
            fill="white",
            font=("Arial", 20, "bold"),
        )
        self.canvas.create_text(
            self.canvas_width // 2,
            self.canvas_height // 2 + 20,
            text=message,
            fill="white",
            font=("Arial", 12),
        )
    def _on_canvas_click(self, event: "tk.Event") -> None:
        """Convert mouse clicks to board coordinates."""
        row = event.y // self.cell_size
        col = event.x // self.cell_size
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.controller.on_cell_click(int(row), int(col))