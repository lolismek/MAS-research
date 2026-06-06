# Dou Dizhu Game

Welcome to the Dou Dizhu Game, a digital implementation of the popular Chinese Poker game for three players. This game is designed to provide an engaging and strategic card-playing experience, where one player becomes the 'landlord' and the others aim to be the first to run out of cards or prevent the landlord from doing so.

## Main Functions

- **Bidding Phase**: Players bid to become the landlord. The highest bidder receives three additional cards and plays against the other two players.
- **Card Combinations**: Play valid combinations such as singles, pairs, straights, and more. The game enforces the rules of Dou Dizhu to ensure fair play.
- **Pass or Beat Logic**: Players must either pass or play a higher combination than the current one on the table.
- **Graphical User Interface**: A simple GUI displays player hands and game status, making it easy to follow the game flow.

## Quick Install

To get started with the Dou Dizhu Game, you'll need to install the necessary environment dependencies. Follow these steps:

1. **Clone the Repository**: First, clone the repository to your local machine.

   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install Dependencies**: Use pip to install the required dependencies.

   ```bash
   pip install -r requirements.txt
   ```

   This will install the `pygame` library, which is essential for running the game's graphical interface.

## How to Play

1. **Start the Game**: Run the main module to initialize and start the game.

   ```bash
   python main.py
   ```

2. **Game Setup**: The game will automatically shuffle the deck and deal 17 cards to each player.

3. **Bidding Phase**: Players will take turns to bid for the role of landlord. The player with the highest bid becomes the landlord and receives three additional cards.

4. **Playing the Game**: Players take turns to play valid card combinations or pass. The objective is to be the first to run out of cards or prevent the landlord from doing so.

5. **Winning the Game**: The game ends when a player has no cards left in their hand. The winner is announced, and the game can be restarted for another round.

## Documentation

For more detailed information on the game's rules and mechanics, please refer to the following sections:

- **Game Rules**: Understand the valid card combinations and the pass-or-beat logic.
- **Player Roles**: Learn about the roles of landlord and peasants and their objectives.
- **Strategy Tips**: Discover strategies to improve your chances of winning.

Enjoy playing Dou Dizhu and may the best strategist win!