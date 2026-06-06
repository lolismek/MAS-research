# Roguelike Game Inspired by Tower of the Sorcerer

Welcome to the user manual for our roguelike game inspired by "Tower of the Sorcerer". This document will guide you through the installation process, introduce you to the main features of the game, and provide instructions on how to play.

## Quick Install

To get started with the game, you need to install the required dependencies. The game is built using Python and the Pygame library.

### Prerequisites

- Python 3.x installed on your system.
- Pygame library.

### Installation Steps

1. **Clone the Repository:**

   First, clone the repository to your local machine using the following command:

   ```bash
   git clone <repository-url>
   ```

2. **Navigate to the Project Directory:**

   ```bash
   cd <project-directory>
   ```

3. **Install Dependencies:**

   Use pip to install the required dependencies listed in the `requirements.txt` file:

   ```bash
   pip install -r requirements.txt
   ```

   This will install the Pygame library, which is necessary to run the game.

## 🤔 What is this?

This game is a roguelike adventure inspired by the classic "Tower of the Sorcerer". It features an 80x80 grid map where players navigate through floors, encounter monsters, and collect treasures. The primary goal is to reach the door to proceed to the next level while managing your health points (HP).

### Main Features

- **Grid-Based Movement:** Navigate the player character using W/A/S/D keys for movement (up, left, down, right) on a fixed 80x80 grid map.
- **Combat System:** Engage in combat with monsters by subtracting their HP from the player's HP.
- **Treasure Collection:** Restore HP by 20–30 points when collecting treasure chests.
- **Pathfinding:** The game ensures there is always at least one valid path from the starting position to the door.
- **Minimal UI:** Displays the player's current HP and encountered monster stats.

## 📖 How to Play

1. **Start the Game:**

   Run the main script to start the game:

   ```bash
   python main.py
   ```

2. **Game Controls:**

   - Use `W` to move up.
   - Use `A` to move left.
   - Use `S` to move down.
   - Use `D` to move right.

3. **Objective:**

   - Navigate through the grid to reach the door and proceed to the next level.
   - Avoid or combat monsters to survive.
   - Collect treasure chests to restore your HP.

4. **User Interface:**

   - The game window displays the grid map, player, monsters, and treasure chests.
   - Your current HP is displayed at the top left corner of the screen.

## Additional Information

For any issues or further assistance, please contact our support team or refer to the documentation provided within the codebase.

Enjoy your adventure in the roguelike world inspired by "Tower of the Sorcerer"!