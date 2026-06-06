```markdown
# Interactive Storytelling Game

An engaging and immersive interactive storytelling game where player decisions influence the storyline, relationships, and possible endings.

## Main Functions

- **Narrative Segments**: The game presents narrative segments that unfold as the player progresses.
- **Branching Choices**: Players are presented with choices that influence subsequent story events.
- **Dynamic Storyline**: Player decisions affect the storyline, relationships, and items, leading to multiple possible endings.
- **Conditional Paths**: Different paths are available based on player choices and conditions.

## Installation

To run the Interactive Storytelling Game, you need to have Python and the required dependencies installed on your system.

### Step 1: Install Python

Ensure Python is installed on your system. You can download it from the [official Python website](https://www.python.org/downloads/).

### Step 2: Install Dependencies

The game requires the `pygame` library. You can install it using pip:

```bash
pip install pygame==2.1.2
```

Alternatively, you can install all dependencies listed in the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

## How to Play

1. **Start the Game**: Run the `main.py` file to start the game.

   ```bash
   python main.py
   ```

2. **Game Interface**: The game window will open, displaying the current narrative segment and available choices.

3. **Making Choices**: Use the keyboard to make choices:
   - Press `1` to select the first choice.
   - Press `2` to select the second choice.

4. **Progression**: The story progresses based on your choices. Your decisions will influence the storyline, relationships, and items in your inventory.

5. **Ending**: The game offers multiple endings based on the paths you choose and the conditions met during the gameplay.

## Game Structure

- **Main.py**: The entry point of the game, initializing the game loop and handling user inputs.
- **Story.py**: Defines the `StoryNode` and `Choice` classes for managing story segments and branching choices.
- **Player.py**: Manages player-related variables such as relationships and inventory.
- **StoryManager.py**: Manages the story nodes and player progress through the game.

Enjoy the adventure and explore the different paths and endings in the Interactive Storytelling Game!
```