'''
Game controller for the Match-3 puzzle game.
Coordinates the board model and GUI interactions.
'''
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
from board import Match3Board
from game_ui import GameUI
@dataclass
class GameConfig:
    rows: int = 8
    cols: int = 8
    candy_types: int = 6
    cell_size: int = 64
    moves_limit: int = 30
    target_score: int = 2000
class GameController:
    """Main controller that manages game state and user interaction."""
    def __init__(self) -> None:
        self.config = GameConfig()
        self.score = 0
        self.moves_left = self.config.moves_limit
        self.selected: Optional[Tuple[int, int]] = None
        self.game_over = False
        self.board = Match3Board(
            rows=self.config.rows,
            cols=self.config.cols,
            candy_types=self.config.candy_types,
        )
        self.ui = GameUI(
            controller=self,
            rows=self.config.rows,
            cols=self.config.cols,
            cell_size=self.config.cell_size,
            target_score=self.config.target_score,
        )
        self.start_new_game()
    def run(self) -> None:
        """Run the tkinter main loop."""
        self.ui.run()
    def start_new_game(self) -> None:
        """Reset the board and game state."""
        self.board.reset()
        self.score = 0
        self.moves_left = self.config.moves_limit
        self.selected = None
        self.game_over = False
        self.ui.clear_game_over_overlay()
        self.ui.set_status("Match candies to score points!")
        self.ui.update_hud(self.score, self.moves_left)
        self.ui.render()
    def on_cell_click(self, row: int, col: int) -> None:
        """Handle a click on a board cell."""
        if self.game_over:
            return
        if self.moves_left <= 0:
            self.end_game("No moves left. Game over!")
            return
        if self.selected is None:
            self.selected = (row, col)
            self.ui.render()
            return
        sr, sc = self.selected
        if (sr, sc) == (row, col):
            self.selected = None
            self.ui.render()
            return
        if self.board.are_adjacent(sr, sc, row, col):
            valid, gained = self.board.try_swap_and_resolve(sr, sc, row, col)
            self.selected = None
            if valid:
                self.moves_left -= 1
                self.score += gained
                self.ui.set_status(f"Cleared {gained} candies! Keep going.")
                self.ui.update_hud(self.score, self.moves_left)
                self.ui.render()
                if self.score >= self.config.target_score:
                    self.end_game("You reached the target score. You win!")
                    return
                if self.moves_left <= 0:
                    self.end_game("No moves left. Game over!")
                    return
                if not self.board.has_any_valid_move():
                    self.end_game("No valid moves remain. Game over!")
                    return
            else:
                self.ui.set_status("Invalid move: swap must create a match.")
                self.ui.render()
        else:
            self.selected = (row, col)
            self.ui.render()
    def end_game(self, message: str) -> None:
        """End the game and show a final message."""
        self.game_over = True
        self.ui.set_status(message)
        self.ui.render()
        self.ui.show_game_over(message)