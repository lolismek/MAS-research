# Match-3 Puzzle Game User Manual

Welcome to the Match-3 Puzzle Game, a fun and engaging game reminiscent of Candy Crush. This manual will guide you through the installation, setup, and gameplay of the Match-3 Puzzle Game.

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Game Features](#game-features)
4. [How to Play](#how-to-play)
5. [Troubleshooting](#troubleshooting)
6. [Contact and Support](#contact-and-support)

## Introduction

The Match-3 Puzzle Game is a classic puzzle game where players swap adjacent candies to form matches of three or more. Matches are cleared, new candies appear, and scoring is tracked. The game incorporates chain reactions when candies fall, providing an exciting and dynamic gameplay experience.

## Installation

To get started with the Match-3 Puzzle Game, you need to install the necessary environment dependencies and set up the game on your system.

### Prerequisites

- Python 3.x
- pip (Python package manager)

### Quick Install

1. **Clone the Repository**

   Clone the game repository from the source:

   ```bash
   git clone <repository-url>
   cd match-3-puzzle-game
   ```

2. **Install Dependencies**

   Use pip to install the required dependencies listed in the `requirements.txt` file:

   ```bash
   pip install -r requirements.txt
   ```

   The main dependency for this game is `pygame`, which is used for rendering graphics and handling user interactions.

## Game Features

- **Interactive Game Board:** An 8x8 grid filled with colorful candies.
- **Candy Swapping:** Swap adjacent candies to form matches of three or more.
- **Match Clearing:** Matches are cleared, and new candies fall into place.
- **Chain Reactions:** Create chain reactions for higher scores.
- **Score Tracking:** Keep track of your score as you play.

## How to Play

1. **Start the Game**

   Run the main script to start the game:

   ```bash
   python main.py
   ```

2. **Game Interface**

   - The game window will open, displaying an 8x8 grid of candies.
   - Your current score will be displayed at the top of the window.

3. **Making Moves**

   - Click on a candy to select it.
   - Click on an adjacent candy to swap them.
   - If the swap results in a match of three or more candies of the same color, the candies will be cleared, and new candies will fall into place.

4. **Scoring**

   - Points are awarded for each candy cleared.
   - Create chain reactions to earn more points.

5. **Game Objective**

   - The objective is to score as many points as possible by creating matches and chain reactions.

## Troubleshooting

- **Game Not Starting:** Ensure that all dependencies are installed correctly. Check for any error messages in the terminal.
- **Graphics Issues:** Make sure your system supports `pygame` and that your graphics drivers are up to date.

## Contact and Support

For further assistance, please contact our support team at support@chatdev.com. We are here to help you with any issues or questions you may have.

Enjoy playing the Match-3 Puzzle Game and challenge yourself to achieve the highest score!