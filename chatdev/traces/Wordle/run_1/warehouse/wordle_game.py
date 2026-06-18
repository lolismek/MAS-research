'''
Core Wordle game logic for a terminal-based implementation.
'''
from collections import Counter
from datetime import date
import os
import sys
from word_list import ANSWER_LIST, VALID_GUESS_LIST
class WordleGame:
    """A terminal Wordle game with 6 attempts and color feedback."""
    MAX_ATTEMPTS = 6
    WORD_LENGTH = 5
    def __init__(self, ansi_enabled=None, fixed_date=None):
        self._validate_word_lists()
        self.answer_words = set(ANSWER_LIST)
        self.valid_words = set(VALID_GUESS_LIST)
        self.ansi_enabled = self._detect_ansi_support() if ansi_enabled is None else bool(ansi_enabled)
        self.fixed_date = fixed_date
        self.answer = self._get_daily_word(fixed_date=fixed_date)
    @staticmethod
    def _validate_word_lists():
        """Validate dictionary integrity at startup."""
        if not ANSWER_LIST:
            raise ValueError("ANSWER_LIST must not be empty.")
        def is_valid_word(word):
            return isinstance(word, str) and len(word) == WordleGame.WORD_LENGTH and word.isalpha()
        invalid_answers = [w for w in ANSWER_LIST if not is_valid_word(w)]
        invalid_guesses = [w for w in VALID_GUESS_LIST if not is_valid_word(w)]
        if invalid_answers:
            raise ValueError(f"Invalid answer words found: {invalid_answers}")
        if invalid_guesses:
            raise ValueError(f"Invalid guess words found: {invalid_guesses}")
        missing_answers = [w for w in ANSWER_LIST if w not in VALID_GUESS_LIST]
        if missing_answers:
            raise ValueError(
                "Every answer must be included in VALID_GUESS_LIST or explicitly accepted. "
                f"Missing: {missing_answers}"
            )
    @staticmethod
    def _detect_ansi_support():
        """Detect whether ANSI colors are likely supported."""
        if not sys.stdout.isatty():
            return False
        term = os.environ.get("TERM", "").lower()
        if term in {"dumb", ""}:
            return False
        return True
    def _get_daily_word(self, fixed_date=None):
        """
        Return a deterministic daily word based on the current calendar date.
        The same date always maps to the same word across all environments.
        Optionally accepts a fixed date for testing.
        """
        day = fixed_date if fixed_date is not None else date.today()
        if not isinstance(day, date):
            raise TypeError("fixed_date must be a datetime.date instance or None.")
        index = day.toordinal() % len(ANSWER_LIST)
        return ANSWER_LIST[index]
    def _validate_guess(self, guess):
        """Validate that the guess is a legal 5-letter word."""
        guess = guess.strip().lower()
        if len(guess) != self.WORD_LENGTH:
            return False, f"Guess must be exactly {self.WORD_LENGTH} letters."
        if not guess.isalpha():
            return False, "Guess must contain only alphabetic characters."
        if guess not in self.valid_words:
            return False, "Word not in accepted word list."
        return True, ""
    def _score_guess(self, guess):
        """
        Score a guess against the answer using Wordle rules.
        Returns a list of tuples: (letter, status)
        where status is one of:
        - green: correct letter and correct position
        - yellow: correct letter but wrong position
        - grey: letter not in the word
        """
        guess = guess.lower().strip()
        answer = self.answer.lower()
        if len(guess) != self.WORD_LENGTH:
            raise ValueError(f"Invalid guess length: expected {self.WORD_LENGTH}, got {len(guess)}")
        result = ["grey"] * self.WORD_LENGTH
        answer_counts = Counter(answer)
        for i in range(self.WORD_LENGTH):
            if guess[i] == answer[i]:
                result[i] = "green"
                answer_counts[guess[i]] -= 1
        for i in range(self.WORD_LENGTH):
            if result[i] == "green":
                continue
            if answer_counts[guess[i]] > 0:
                result[i] = "yellow"
                answer_counts[guess[i]] -= 1
        return list(zip(guess, result))
    def _format_colored_output(self, scored_guess):
        """Format a scored guess using ANSI colors or plain-text markers."""
        if self.ansi_enabled:
            colors = {
                "green": "\033[1;42m\033[30m",
                "yellow": "\033[1;43m\033[30m",
                "grey": "\033[1;100m\033[37m",
                "reset": "\033[0m",
            }
            blocks = []
            for letter, status in scored_guess:
                blocks.append(f"{colors[status]} {letter.upper()} {colors['reset']}")
            return " ".join(blocks)
        markers = {
            "green": "[G]",
            "yellow": "[Y]",
            "grey": "[.]",
        }
        blocks = []
        for letter, status in scored_guess:
            blocks.append(f"{markers[status]}{letter.upper()}")
        return " ".join(blocks)
    def _read_guess(self, prompt):
        """Read a guess safely, returning None if input is unavailable."""
        try:
            return input(prompt)
        except EOFError:
            return None
        except KeyboardInterrupt:
            return None
    def play(self):
        """Start the interactive terminal game."""
        print("=" * 40)
        print("WORDLE - Terminal Edition")
        print("=" * 40)
        print(f"Date: {date.today().isoformat()}")
        print(f"Guess the {self.WORD_LENGTH}-letter word in {self.MAX_ATTEMPTS} attempts.")
        print("Feedback: Green = correct position, Yellow = wrong position, Grey = not in word.")
        if not self.ansi_enabled:
            print("ANSI colors unavailable; using plain-text markers.")
        print()
        attempt = 0
        while attempt < self.MAX_ATTEMPTS:
            remaining = self.MAX_ATTEMPTS - attempt
            guess = self._read_guess(
                f"Attempt {attempt + 1}/{self.MAX_ATTEMPTS} ({remaining} left): "
            )
            if guess is None:
                print("\nInput unavailable. Exiting game gracefully.")
                return
            guess = guess.strip().lower()
            valid, message = self._validate_guess(guess)
            if not valid:
                print(f"Invalid guess: {message}")
                continue
            scored = self._score_guess(guess)
            print(self._format_colored_output(scored))
            print()
            attempt += 1
            if guess == self.answer:
                print("🎉 Congratulations! You guessed the word!")
                return
        print(f"Game over. The correct word was: {self.answer.upper()}")