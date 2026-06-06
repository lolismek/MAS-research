# Reversi (Othello) Game User Manual

Welcome to the Reversi (Othello) Game, a classic board game brought to life through the power of Python and Pygame. This manual will guide you through the installation, setup, and gameplay of the Reversi game.

## Quick Install

To get started with the Reversi game, you need to install the required dependencies. Follow the steps below to set up your environment:

1. **Ensure Python is Installed**: Make sure you have Python installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

2. **Install Pygame**: Pygame is a set of Python modules designed for writing video games. You can install it using pip:

   ```bash
   pip install pygame==2.1.2
   ```

3. **Clone the Repository**: Download the game code from the repository or copy the provided code files (`main.py`, `game.py`, `board.py`) into a directory on your computer.

## 🤔 What is this?

Reversi, also known as Othello, is a strategy board game for two players. The game is played on an 8x8 board with discs that are black on one side and white on the other. Players take turns placing discs on the board with their assigned color facing up. The objective is to have the majority of discs turned to display your color when the last playable empty square is filled.

### Main Features

- **Automatic Move Validation**: The game automatically identifies valid moves for the current player.
- **Disc Flipping**: Discs are flipped automatically when a valid move is made.
- **Score Display**: The current score is displayed, showing the number of discs for each player.
- **Game End Detection**: The game ends when the board is full or no valid moves remain, and the winner is announced.

## 📖 How to Play

1. **Start the Game**: Run the `main.py` file to start the game. You can do this by navigating to the directory containing the game files in your terminal or command prompt and executing:

   ```bash
   python main.py
   ```

2. **Gameplay**:
   - The game window will open with an 8x8 grid.
   - Players alternate turns, starting with the black player ('B').
   - Click on a valid empty square to place your disc. Valid moves will automatically be highlighted.
   - The game will automatically flip the opponent's discs that are between the newly placed piece and existing pieces of the same color.
   - The current score will be displayed in the console.

3. **Winning the Game**:
   - The game ends when the board is full or no valid moves remain for both players.
   - The player with the most discs of their color on the board is declared the winner.
   - If both players have the same number of discs, the game is a draw.

## Additional Information

For any issues or questions, please refer to the Pygame documentation or contact the support team. Enjoy playing Reversi and may the best strategist win!

---

This manual provides all the necessary information to install, set up, and enjoy the Reversi (Othello) game. Happy gaming!