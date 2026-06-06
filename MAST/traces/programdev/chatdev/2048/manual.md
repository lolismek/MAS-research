```markdown
# 2048 Game

A classic 2048 game built using Python and Pygame, where players combine tiles by pressing arrow keys to slide them in one direction. Tiles with the same number merge into one, doubling the value. After each move, a new tile appears in a random empty cell. The game ends when no moves are possible. The game tracks and displays the current score and the highest tile reached.

## Quick Install

To get started with the 2048 game, you need to install the required dependencies. The game is built using Python and Pygame, so make sure you have Python installed on your system.

1. **Install Pygame**: You can install Pygame using pip. Open your terminal or command prompt and run the following command:

    ```bash
    pip install pygame==2.1.2
    ```

2. **Clone the Repository**: Clone the repository containing the game code to your local machine.

    ```bash
    git clone <repository-url>
    ```

3. **Navigate to the Project Directory**: Change your directory to the project folder.

    ```bash
    cd <project-directory>
    ```

## 🤔 What is this?

The 2048 game is a single-player sliding tile puzzle game. The objective is to slide numbered tiles on a grid to combine them and create a tile with the number 2048. The game is simple yet challenging, requiring strategic thinking and planning.

## 📖 How to Play

1. **Start the Game**: Run the main Python script to start the game.

    ```bash
    python main.py
    ```

2. **Game Controls**: Use the arrow keys on your keyboard to move the tiles in the desired direction:
   - **Up Arrow**: Move tiles up.
   - **Down Arrow**: Move tiles down.
   - **Left Arrow**: Move tiles left.
   - **Right Arrow**: Move tiles right.

3. **Objective**: Combine tiles with the same number to double their value. Try to reach the 2048 tile!

4. **Game Over**: The game ends when no more moves are possible. Your score and the highest tile reached will be displayed.

## Features

- **Grid Management**: The game uses a 4x4 grid to manage tiles.
- **Tile Merging**: Tiles with the same number merge into one, doubling the value.
- **Random Tile Generation**: After each move, a new tile (2 or 4) appears in a random empty cell.
- **Score Tracking**: The game tracks and displays the current score.
- **Highest Tile Tracking**: The game displays the highest tile reached during the session.

## Documentation

For more detailed information on the game's implementation and code structure, please refer to the source code files:

- **main.py**: The main entry point for the game application.
- **game.py**: Contains the game logic, including state management and tile operations.
- **gui.py**: Handles the graphical user interface using Pygame.

Enjoy playing the 2048 game and challenge yourself to reach the highest tile possible!
```
