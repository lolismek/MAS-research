```markdown
# Terminal Chess Game

A simple chess game designed to be played in the Linux Terminal. This game allows two players to take turns and determine the winner. It includes standard chess features such as castling, en passant, and pawn promotion, and enforces check and checkmate rules.

## Quick Install

This chess game is implemented in Python and does not require any external dependencies. To get started, ensure you have Python installed on your system.

### Installation Steps

1. **Clone the Repository:**

   Clone the repository to your local machine using the following command:

   ```bash
   git clone <repository-url>
   ```

   Replace `<repository-url>` with the actual URL of the repository.

2. **Navigate to the Project Directory:**

   Change your directory to the project folder:

   ```bash
   cd <project-directory>
   ```

   Replace `<project-directory>` with the name of the directory where the repository was cloned.

3. **Run the Game:**

   Execute the main Python script to start the game:

   ```bash
   python main.py
   ```

## 🤔 What is this?

This is a terminal-based chess game that allows two players to play against each other using standard chess rules. The game is designed to run in a Linux terminal and does not require a graphical user interface.

### Main Features

- **Standard Chess Rules:** The game includes all standard chess rules, such as castling, en passant, and pawn promotion.
- **Check and Checkmate:** The game enforces check and checkmate rules to determine the winner.
- **Terminal Interface:** The game is played entirely in the terminal, with the board displayed after each move.
- **Input Moves:** Players input their moves using formal chess notation (e.g., `Ke8`).

## 📖 How to Play

1. **Start the Game:**

   Run the `main.py` script to start the game. The chessboard will be displayed in the terminal.

2. **Enter Moves:**

   Players take turns entering their moves using standard chess notation. For example, to move a knight to e8, type `Ne8`.

3. **Game Progression:**

   After each move, the updated board will be displayed. The game will continue until a player wins by checkmate or the game ends in a stalemate.

4. **Special Moves:**

   - **Castling:** If castling is possible, you can perform it by moving the king two squares towards the rook.
   - **En Passant:** If en passant is possible, capture the pawn by moving your pawn to the target square.
   - **Pawn Promotion:** When a pawn reaches the opposite end of the board, you will be prompted to promote it to a queen, rook, bishop, or knight.

5. **Winning the Game:**

   The game ends when a player checkmates the opponent's king, or if a stalemate occurs, resulting in a draw.

Enjoy playing chess in your terminal!
```
