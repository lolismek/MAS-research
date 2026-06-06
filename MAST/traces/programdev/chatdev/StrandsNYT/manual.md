# NYT Strands Puzzle Game

Welcome to the NYT Strands Puzzle Game! This is a word search game where players uncover words within a 6x8 grid of letters. The game includes themed words and a special challenge word called the "spangram" that spans two opposite sides of the board. Themed words will highlight blue, while the spangram will highlight yellow. Players can also find non-theme words to earn hints. Every 3 non-theme words will unlock a hint!

## Main Features

- **Themed Words**: Discover words that fall under a specific theme. These words will be highlighted in blue.
- **Spangram**: A special challenge word that touches two opposite sides of the board, highlighted in yellow.
- **Non-Theme Words**: Find additional words to earn hints. Every 3 non-theme words found will unlock a hint.
- **Interactive Board**: Click on the grid to uncover words and track your progress.
- **Hints System**: Keep track of hints earned through non-theme words.

## Installation

### Environment Setup

This project does not require any external dependencies, making it easy to set up and run. Ensure you have Python installed on your system.

### Quick Install

1. **Clone the Repository**: 
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Run the Game**:
   ```bash
   python main.py
   ```

## How to Play

1. **Start the Game**: Run the `main.py` file to launch the game interface.
2. **Explore the Grid**: Click on the cells in the 6x8 grid to uncover letters and form words.
3. **Find Themed Words**: Look for words that fit the given theme. These will be highlighted in blue.
4. **Discover the Spangram**: Identify the special challenge word that spans two opposite sides of the board. This word will be highlighted in yellow.
5. **Earn Hints**: Find non-theme words to earn hints. Every 3 non-theme words will unlock a hint, which can assist in finding themed words.
6. **Complete the Puzzle**: The puzzle is complete when all themed words are found, and the board is fully filled.

## Documentation

For further details on the code structure and logic, please refer to the following files:

- **main.py**: Initializes the game interface and manages the game loop.
- **game_board.py**: Handles the creation and management of the game board, including placing words and checking for completion.
- **word.py**: Represents individual words on the board, including their position, direction, and type.
- **hint_system.py**: Manages the unlocking of hints based on non-theme words found.

Enjoy playing the NYT Strands Puzzle Game and challenge yourself to uncover all the words!