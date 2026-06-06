```markdown
# Monopoly Go! Simplified Version

Welcome to the user manual for the simplified version of Monopoly Go! This application is a digital adaptation of the classic board game, designed to provide an engaging experience with basic board mechanics. This manual will guide you through the main functions of the software, how to install the necessary environment dependencies, and how to play the game.

## Main Functions

Monopoly Go! includes the following core features:

- **Rolling Dice**: Players roll two six-sided dice to determine their movement around the board.
- **Moving Around Properties**: Players move their tokens around the board based on the dice roll.
- **Buying Properties**: Players can purchase properties they land on if they are not already owned.
- **Collecting Rent**: Players must pay rent to the property owner when landing on a property owned by another player.
- **Handling Chance Events**: Players draw chance cards that can have various effects, such as going to jail or collecting money.
- **Tracking Player Money and Property Ownership**: The game keeps track of each player's money and the properties they own.
- **Implementing Essential Rules**: Includes simplified rules for jail, free parking, and chance cards.

## Installation

To run Monopoly Go!, you need to have Python installed on your system. Additionally, the game requires the `pygame` library for graphical elements. Follow these steps to set up your environment:

1. **Install Python**: Ensure you have Python 3.x installed. You can download it from [python.org](https://www.python.org/downloads/).

2. **Install Dependencies**: Use pip to install the required dependencies. Open your terminal or command prompt and run the following command:

   ```bash
   pip install -r requirements.txt
   ```

   This will install the `pygame` library, which is necessary for running the game.

## How to Play

1. **Start the Game**: Run the `main.py` file to start the game. You can do this by navigating to the directory containing the game files in your terminal or command prompt and executing:

   ```bash
   python main.py
   ```

2. **Game Interface**: The game will open a window displaying the board and player positions. The game is played in turns, with each player rolling the dice and moving their token accordingly.

3. **Player Actions**: During a player's turn, they can perform the following actions:
   - **Roll Dice**: Automatically done at the start of each turn.
   - **Move**: The player moves their token based on the dice roll.
   - **Buy Property**: If the player lands on an unowned property, they can choose to buy it.
   - **Pay Rent**: If the player lands on a property owned by another player, they must pay rent.
   - **Chance Cards**: If the player lands on a chance space, a card is drawn, and its effect is applied.

4. **Game End**: The game continues until a player is bankrupt (money less than 0 and no properties), at which point the game ends, and a winner is declared.

5. **Exiting the Game**: You can exit the game at any time by closing the game window.

Enjoy playing Monopoly Go! and may the best strategist win!
```