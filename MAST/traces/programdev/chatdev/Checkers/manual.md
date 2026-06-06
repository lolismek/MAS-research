# Checkers Game User Manual

Welcome to the Checkers Game application! This user manual will guide you through the installation process, introduce the main features of the game, and provide instructions on how to play.

## Overview

The Checkers Game is a digital version of the classic board game, designed to be played on an 8x8 board. The game alternates turns between two players, applying standard capture and kinging rules. Players input their moves using standard notation (e.g., A3-B4), and the game updates the board state accordingly.

## Quick Install

To get started with the Checkers Game, you need to install the required dependencies. The game is built using Python and the Pygame library.

### Prerequisites

- Python 3.x installed on your system.
- Pygame library for rendering the game interface.

### Installation Steps

1. **Clone the Repository:**

   First, clone the repository to your local machine using the following command:

   ```bash
   git clone <repository-url>
   ```

2. **Navigate to the Project Directory:**

   Change into the project directory:

   ```bash
   cd <repository-directory>
   ```

3. **Install Dependencies:**

   Install the required dependencies using pip:

   ```bash
   pip install -r requirements.txt
   ```

   This will install the Pygame library, which is necessary to run the game.

## How to Play

### Starting the Game

To start the game, run the `main.py` script:

```bash
python main.py
```

This will launch the game window with an 8x8 board displayed.

### Game Rules

- **Objective:** The goal is to capture all of the opponent's pieces or block them so they cannot make a move.
- **Turns:** Players alternate turns, with the white player starting first.
- **Movement:** Pieces move diagonally forward. If a piece reaches the opposite end of the board, it becomes a "king" and can move diagonally both forward and backward.
- **Capturing:** You can capture an opponent's piece by jumping over it diagonally to an empty square immediately beyond it.
- **Kinging:** When a piece reaches the farthest row from its starting position, it is "kinged" and gains the ability to move backward.

### Inputting Moves

- Enter your move in the format `A3-B4`, where `A3` is the starting position and `B4` is the destination.
- The game will validate the move and update the board accordingly.
- If the move is invalid, an error message will be displayed, and you will be prompted to enter a new move.

### Ending the Game

The game ends when one player captures all of the opponent's pieces or blocks them from making any legal moves.

## Troubleshooting

- **Invalid Move:** Ensure that your move follows the rules of Checkers. Check for correct notation and valid piece movement.
- **Game Not Starting:** Verify that Python and Pygame are correctly installed. Check for any error messages in the terminal for further guidance.

## Additional Resources

For more information on the rules of Checkers, you can refer to [Wikipedia's Checkers Page](https://en.wikipedia.org/wiki/Draughts).

Thank you for choosing our Checkers Game! We hope you enjoy playing. If you encounter any issues or have feedback, please contact our support team.