'''
This script implements a terminal-based Wordle game. The player has six attempts to guess a daily 5-letter word. Feedback is provided for each guess, indicating correct letters in the correct position (green), correct letters in the wrong position (yellow), and incorrect letters (grey).
'''
import random
class WordleGame:
    def __init__(self, target_word):
        self.target_word = target_word
        self.max_attempts = 6
        self.attempts = 0
    def check_guess(self, guess):
        feedback = ['grey'] * 5
        target_word_list = list(self.target_word)
        # First pass: check for correct letters in correct positions
        for i in range(5):
            if guess[i] == self.target_word[i]:
                feedback[i] = 'green'
                target_word_list[i] = None  # Remove matched letter
        # Second pass: check for correct letters in wrong positions
        for i in range(5):
            if feedback[i] == 'grey' and guess[i] in target_word_list:
                feedback[i] = 'yellow'
                target_word_list[target_word_list.index(guess[i])] = None  # Remove matched letter
        return feedback
    def play(self):
        print("Welcome to Wordle!")
        print("You have 6 attempts to guess the 5-letter word.")
        while self.attempts < self.max_attempts:
            guess = input(f"Attempt {self.attempts + 1}: ").strip().lower()
            if not self.validate_word(guess):
                print("Invalid word. Please enter a 5-letter word.")
                continue
            self.attempts += 1
            feedback = self.check_guess(guess)
            # Display feedback
            feedback_display = ''.join([f"[{feedback[i]}]" for i in range(5)])
            print(f"Feedback: {feedback_display}")
            if feedback == ['green'] * 5:
                print("Congratulations! You've guessed the word!")
                return
        print(f"Sorry, you've used all attempts. The word was: {self.target_word}")
    def validate_word(self, word):
        return len(word) == 5 and word.isalpha()
def get_daily_word():
    # For simplicity, we'll use a fixed list of words. In a real application, this could be replaced with a more dynamic source.
    words = ["apple", "grape", "peach", "berry", "melon"]
    return random.choice(words)
if __name__ == "__main__":
    daily_word = get_daily_word()
    game = WordleGame(daily_word)
    game.play()