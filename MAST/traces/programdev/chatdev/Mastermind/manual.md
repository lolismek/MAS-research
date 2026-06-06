```markdown
# Mastermind Game

Welcome to the Mastermind Game! This classic code-breaking game challenges you to guess a hidden sequence of colors within a set number of tries. After each guess, you'll receive feedback on how many colors are correct and in the correct position, as well as how many colors are correct but in the wrong position. Can you crack the code before your attempts run out?

## Quick Install

To get started with the Mastermind Game, ensure you have Python installed on your system. The game uses the `tkinter` library, which is part of the Python standard library, so no additional external packages are required.

### Requirements

- Python version 3.6 or higher

### Installation Steps

1. **Clone the Repository:**

   Clone the repository to your local machine using the following command:

   ```bash
   git clone <repository-url>
   ```

   Replace `<repository-url>` with the actual URL of the repository.

2. **Navigate to the Project Directory:**

   Change into the project directory:

   ```bash
   cd <project-directory>
   ```

   Replace `<project-directory>` with the actual directory name.

3. **Run the Game:**

   Execute the following command to start the game:

   ```bash
   python main.py
   ```

## 🤔 What is this?

The Mastermind Game is a fun and challenging puzzle game where the computer selects a hidden sequence of colors, and you attempt to guess it within a set number of tries. The game provides feedback on your guesses, helping you to deduce the correct sequence.

### Main Features

- **Random Code Generation:** The computer randomly selects a sequence of colors from a predefined set.
- **Feedback System:** After each guess, receive feedback on exact matches (correct color and position) and color matches (correct color, wrong position).
- **Win/Lose Outcome:** The game provides a clear win or lose outcome based on your ability to guess the sequence within the allowed attempts.

## 📖 How to Play

1. **Start the Game:**

   Launch the game by running `python main.py`. A graphical user interface (GUI) will appear.

2. **Enter Your Guess:**

   - Enter your guess in the provided input fields. Each field represents a color in the sequence.
   - Use the following color codes: R (Red), G (Green), B (Blue), Y (Yellow), O (Orange), P (Purple).

3. **Submit Your Guess:**

   - Click the "Submit Guess" button to submit your guess.
   - The game will provide feedback on your guess, indicating the number of exact matches and color matches.

4. **Win or Lose:**

   - If you guess the correct sequence within the allowed attempts, you win!
   - If you use all your attempts without guessing the sequence, the game will reveal the correct code.

Enjoy playing the Mastermind Game and challenge yourself to crack the code!

```