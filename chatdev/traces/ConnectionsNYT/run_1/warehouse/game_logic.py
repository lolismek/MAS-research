'''
core game engine and game state management
'''
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Tuple
import random
from puzzle_data import Puzzle
@dataclass
class GameState:
    """Tracks the current state of the puzzle game."""
    puzzle: Puzzle
    shuffled_words: List[str] = field(default_factory=list)
    selected_words: List[str] = field(default_factory=list)
    solved_groups: List[Tuple[str, str, List[str]]] = field(default_factory=list)
    mistakes: int = 0
    max_mistakes: int = 4
    game_over: bool = False
    won: bool = False
    def remaining_words(self) -> List[str]:
        """Return words not yet solved."""
        solved: Set[str] = set()
        for _, _, words in self.solved_groups:
            solved.update(words)
        return [w for w in self.shuffled_words if w not in solved]
class PuzzleGameEngine:
    """
    Contains the rules and operations for the puzzle game.
    The engine validates guesses, tracks solved groups, and supports shuffling
    only the unsolved portion of the board while preserving a clean 4x4 layout
    for the active puzzle.
    """
    def __init__(self, puzzle: Puzzle) -> None:
        self.state = GameState(puzzle=puzzle, shuffled_words=puzzle.words[:])
    def shuffle(self) -> List[str]:
        """
        Shuffle the remaining unsolved words while keeping solved groups out of
        the active board.
        This maintains a readable board made only of the currently playable
        words. Solved words are excluded from the interactive grid.
        """
        remaining = self.state.remaining_words()
        rng = random.Random()
        rng.shuffle(remaining)
        self.state.shuffled_words = remaining
        return self.state.shuffled_words
    def toggle_selection(self, word: str) -> tuple[bool, str]:
        """
        Select or deselect a word.
        Returns (changed, message). The engine explicitly blocks selection of a
        fifth word and reports why, so the UI can provide immediate feedback.
        """
        if self.state.game_over or self.is_word_solved(word):
            return False, "That word can no longer be selected."
        if word in self.state.selected_words:
            self.state.selected_words.remove(word)
            return True, "Word deselected."
        if len(self.state.selected_words) >= 4:
            return False, "You can only select four words at a time."
        self.state.selected_words.append(word)
        return True, "Word selected."
    def submit_guess(self) -> Tuple[bool, str, str | None]:
        """
        Evaluate the current selection and return immediate feedback.
        Returns: (success, message, category difficulty)
        """
        if self.state.game_over:
            return False, "Game over.", None
        if len(self.state.selected_words) != 4:
            return False, "Select exactly four words.", None
        selected_set = set(self.state.selected_words)
        for _, _, words in self.state.solved_groups:
            if selected_set == set(words):
                self.state.selected_words.clear()
                return False, "That group is already solved.", None
        for category, difficulty, words in self.state.puzzle.groups:
            if selected_set == set(words):
                self.state.solved_groups.append((category, difficulty, words[:]))
                self.state.selected_words.clear()
                if len(self.state.solved_groups) == 4:
                    self.state.game_over = True
                    self.state.won = True
                return True, f"Correct! {category}", difficulty
        self.state.mistakes += 1
        self.state.selected_words.clear()
        if self.state.mistakes >= self.state.max_mistakes:
            self.state.game_over = True
            self.state.won = False
            return False, "Incorrect. You have lost the puzzle.", None
        return False, f"Incorrect. Mistakes: {self.state.mistakes}/{self.state.max_mistakes}", None
    def is_word_solved(self, word: str) -> bool:
        """Check whether a word is already part of a solved group."""
        for _, _, words in self.state.solved_groups:
            if word in words:
                return True
        return False