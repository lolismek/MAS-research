'''
Logic for the Mastermind game.
'''
import random
class MastermindGame:
    def __init__(self, sequence_length=4, max_attempts=10):
        self.sequence_length = sequence_length
        self.max_attempts = max_attempts
        self.colors = ['R', 'G', 'B', 'Y', 'O', 'P']  # Example color set
        self.secret_code = self.generate_secret_code()
        self.attempts = 0
    def generate_secret_code(self):
        return [random.choice(self.colors) for _ in range(self.sequence_length)]
    def check_guess(self, guess):
        if len(guess) != self.sequence_length:
            return "Invalid guess length.", False
        self.attempts += 1
        exact_matches = sum(1 for i in range(self.sequence_length) if guess[i] == self.secret_code[i])
        # Create copies of guess and secret_code to track unmatched colors
        unmatched_guess = [guess[i] for i in range(self.sequence_length) if guess[i] != self.secret_code[i]]
        unmatched_code = [self.secret_code[i] for i in range(self.sequence_length) if guess[i] != self.secret_code[i]]
        # Calculate color matches
        color_matches = sum(min(unmatched_guess.count(c), unmatched_code.count(c)) for c in set(unmatched_guess))
        feedback = f"Exact matches: {exact_matches}, Color matches: {color_matches}"
        win = exact_matches == self.sequence_length
        if win:
            return feedback, True
        elif self.attempts >= self.max_attempts:
            return f"{feedback}. You've used all attempts! The code was {''.join(self.secret_code)}.", False
        else:
            return feedback, False