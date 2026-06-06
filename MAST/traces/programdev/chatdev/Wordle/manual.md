```markdown
# Wordle Game

A terminal-based Wordle game where players have six attempts to guess a daily 5-letter word. Feedback is provided for each guess, indicating correct letters in the correct position (green), correct letters in the wrong position (yellow), and incorrect letters (grey).

## Quick Install

No external dependencies are required for this game. Ensure you have Python installed on your system.

## 🤔 What is this?

This is a simple implementation of the popular Wordle game, designed to be played directly from the Linux Terminal. The game selects a random 5-letter word each day, and players have six attempts to guess it. Feedback is provided after each guess to help players deduce the correct word.

## 📖 How to Play

1. **Start the Game**: Run the `main.py` script using Python in your terminal.
   ```bash
   python main.py
   ```

2. **Game Instructions**: Once the game starts, you will see a welcome message and instructions on how many attempts you have.

3. **Make a Guess**: Enter a 5-letter word when prompted. Your input will be validated to ensure it is a valid 5-letter word.

4. **Receive Feedback**: After each guess, you will receive feedback:
   - `[green]` indicates a correct letter in the correct position.
   - `[yellow]` indicates a correct letter in the wrong position.
   - `[grey]` indicates an incorrect letter.

5. **Win or Lose**: If you guess the word correctly within six attempts, you win! If not, the correct word will be revealed after all attempts are used.

## Example Gameplay

```plaintext
Welcome to Wordle!
You have 6 attempts to guess the 5-letter word.
Attempt 1: apple
Feedback: [green][grey][grey][grey][grey]
Attempt 2: grape
Feedback: [grey][green][grey][grey][grey]
Attempt 3: peach
Feedback: [green][green][green][green][green]
Congratulations! You've guessed the word!
```

## Additional Information

- **Daily Word**: The game selects a random word from a predefined list each time it is played. This list can be expanded or modified in the `get_daily_word` function within the `main.py` file.
- **Customization**: Feel free to modify the word list or game rules to suit your preferences.

Enjoy playing Wordle in your terminal!
```