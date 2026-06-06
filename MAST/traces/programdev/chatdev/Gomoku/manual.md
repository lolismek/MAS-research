# Gomoku Game User Manual

Welcome to the Gomoku Game! This manual will guide you through the installation, setup, and gameplay of the Gomoku game developed using Python and Pygame.

## Introduction

Gomoku, also known as Five in a Row, is a traditional board game played on a 15x15 grid. Two players alternate placing black and white stones on the board. The objective is to be the first player to form an unbroken row of five stones horizontally, vertically, or diagonally.

## Quick Install

To get started with the Gomoku game, you need to install the required dependencies. Follow the steps below:

1. **Clone the Repository:**

   Clone the repository to your local machine using the following command:

   ```bash
   git clone <repository-url>
   ```

2. **Navigate to the Project Directory:**

   Change your directory to the project folder:

   ```bash
   cd <project-directory>
   ```

3. **Install Dependencies:**

   Install the required dependencies using pip:

   ```bash
   pip install -r requirements.txt
   ```

   Ensure you have Python and pip installed on your system. The game requires Pygame version 2.0.0 or higher.

## How to Play

Once you have installed the dependencies, you can start playing the Gomoku game by following these steps:

1. **Run the Game:**

   Execute the main script to start the game:

   ```bash
   python main.py
   ```

2. **Game Interface:**

   - The game window will open, displaying a 15x15 grid.
   - The game starts with the black player making the first move.

3. **Placing Stones:**

   - Click on an empty cell on the board to place your stone.
   - Players alternate turns, with black and white stones.

4. **Winning the Game:**

   - The first player to align five stones in a row (horizontally, vertically, or diagonally) wins the game.
   - A message will display the winner, and the game will reset for a new round.

5. **Exiting the Game:**

   - To exit the game, close the game window or press the close button.

## Main Functions

- **GomokuGame Class:**
  - Manages the game logic, including board setup, stone placement, and win condition checks.

- **GomokuGUI Class:**
  - Handles the graphical user interface using Pygame, including drawing the board and handling user interactions.

- **Main Function:**
  - Initializes and runs the Gomoku game, setting up the GUI and starting the game loop.

## Additional Information

For any issues or questions, please refer to the documentation or contact the support team. Enjoy playing Gomoku and challenge your friends to see who can master the game first!

Happy Gaming!