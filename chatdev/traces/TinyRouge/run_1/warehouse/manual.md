```md
# Tower of the Sorcerer - Roguelike User Manual

A lightweight Python roguelike inspired by *Tower of the Sorcerer*, built with a fixed **80x80 grid map**, simple keyboard controls, procedural level generation, and minimal combat/loot mechanics.

---

## 1. Overview

This game is a tile-based roguelike where you control a player character through a dungeon-like tower. Your goal is to:

- Explore the map
- Avoid walls
- Collect treasure chests to restore HP
- Defeat monsters through direct HP subtraction combat
- Reach the door to advance to the next level

The game always generates a map with **at least one valid path** from the start position to the door.

---

## 2. Main Features

### Fixed 80x80 Grid
- The world is rendered on a fixed **80x80 tile map**.
- Each tile is either:
  - **Wall**
  - **Floor**
  - **Door**
  - **Chest**
  - **Monster**
  - **Player**

### Movement
- Use **W / A / S / D** to move:
  - **W**: Up
  - **A**: Left
  - **S**: Down
  - **D**: Right
- The player can only move on **floor tiles**.
- The player **cannot move through walls**.

### Door and Level Progression
- The **door** is the exit to the next level.
- When the player reaches the door:
  - The next level is generated
  - The player is moved to the new level’s start position

### Combat
- When the player steps onto a monster tile:
  - Combat is resolved instantly
  - The monster’s HP is subtracted from the player’s HP
  - The monster is removed after the encounter

### Treasure Chests
- When the player steps onto a chest:
  - HP is restored by **20–30 points**
  - The chest disappears after being collected

### Minimal UI
The right-side panel displays:
- Current level
- Player HP
- Control instructions
- Status message
- Last encountered monster stats

---

## 3. Requirements

### Software Requirements
- **Python 3.10+** recommended
- **pygame** library

### Operating System
- Windows / macOS / Linux

---

## 4. Installation

### 4.1 Create a Virtual Environment

It is recommended to use a virtual environment.

#### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4.2 Install Dependencies

Install the required package:

```bash
pip install pygame
```

If you want to keep dependencies in a file, you can also create a `requirements.txt` containing:

```txt
pygame
```

Then install with:

```bash
pip install -r requirements.txt
```

---

## 5. Project Structure

Typical files in this project:

```text
main.py
game.py
mapgen.py
tilemap.py
entities.py
manual.md
```

### File Responsibilities
- **main.py**  
  Starts the game application.

- **game.py**  
  Contains the game loop, input handling, rendering, combat, and level progression.

- **mapgen.py**  
  Generates the 80x80 map and guarantees a valid path from start to door.

- **tilemap.py**  
  Stores the map layout and provides helper methods for collision and entity interaction.

- **entities.py**  
  Defines the player, monster, and chest data structures.

---

## 6. How to Run

Run the game with:

```bash
python main.py
```

A game window will open showing:
- The dungeon map on the left
- The HUD panel on the right

---

## 7. How to Play

### Basic Controls
- **W**: move up
- **A**: move left
- **S**: move down
- **D**: move right

### Objective
Reach the **green door** to proceed to the next level.

### What You Will See
- **Blue tile**: player
- **Gray/Light tiles**: floor
- **Dark tiles**: walls
- **Red tiles**: monsters
- **Yellow tiles**: treasure chests
- **Green tile**: door

---

## 8. Game Rules

### Movement Rules
- You can only move onto **floor tiles**
- Walls block movement
- Out-of-bounds movement is blocked automatically

### Combat Rules
- Touching a monster triggers combat immediately
- Combat formula:
  - `player_hp -= monster_hp`
- If HP reaches 0 or below:
  - The game ends
  - You can press **R** to restart

### Chest Rules
- Touching a chest restores:
  - **20 to 30 HP**
- The chest is removed after use
- HP cannot exceed the maximum limit

### Level Rules
- Entering the door advances to the next level
- Each level is procedurally generated
- The generator ensures the door is reachable from the start

---

## 9. User Interface Guide

The HUD panel on the right shows:

### Displayed Information
- **Level**: current dungeon level
- **HP**: current player HP
- **Controls**: movement keys
- **Status**: current game message
- **Last Monster**:
  - HP
  - Position

### Status Messages
Examples include:
- `Use W/A/S/D to move.`
- `A wall blocks your way.`
- `Found a chest. Recovered 25 HP.`
- `Encountered monster: -12 HP.`
- `You reached the door. Next level!`
- `Game Over. Press R to restart.`

---

## 10. Restarting the Game

If the player dies:
- The game enters **Game Over**
- Press **R** to restart from level 1 with 100 HP

---

## 11. Notes on Map Generation

The map generator:
- Starts from a fully walled 80x80 grid
- Carves a guaranteed path from start to door
- Adds additional open areas and rooms
- Places monsters and chests only on reachable floor tiles

This guarantees:
- The player always has at least one valid route to the door
- Gameplay remains random but solvable

---

## 12. Troubleshooting

### The game window does not open
Make sure `pygame` is installed:

```bash
pip install pygame
```

### Module not found errors
Check that you are running the game from the project directory and that all files are present.

### Controls do nothing
Make sure the game window is focused before pressing keys.

### Game runs slowly
Try closing other applications or lowering display scaling if your system is under heavy load.

---

## 13. End Goal

Your mission in each level is simple:

1. Survive
2. Collect helpful chests
3. Defeat or avoid monsters
4. Find the door
5. Advance deeper into the tower

---

## 14. Enjoy the Game

Good luck exploring the tower!
Use your HP wisely, choose your path carefully, and reach the door to conquer the next level.
```