# Snake Game User Manual

Welcome to the Snake Game! This classic game allows you to control a snake, navigate it around the board, eat food, and grow longer. The game ends if the snake collides with itself or the boundary. Enjoy the challenge with multiple difficulty levels!

## Table of Contents
1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Game Features](#game-features)
4. [How to Play](#how-to-play)
5. [Game Controls](#game-controls)
6. [Difficulty Levels](#difficulty-levels)
7. [Scoring](#scoring)

## Introduction

The Snake Game is a simple yet addictive game where the player controls a snake using directional inputs. The objective is to eat as much food as possible without colliding with the snake's own body or the game boundaries. The game offers multiple difficulty levels to cater to different skill levels.

## Installation

To run the Snake Game, you need to have Python and Pygame installed on your system. Follow the steps below to set up the environment:

1. **Install Python**: Ensure you have Python installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

2. **Install Pygame**: Use the following command to install Pygame, a library used for creating the game interface:

   ```bash
   pip install pygame>=2.0.0
   ```

3. **Download the Game Code**: Clone or download the game code from the repository.

4. **Run the Game**: Navigate to the directory containing the game files and execute the following command to start the game:

   ```bash
   python main.py
   ```

## Game Features

- **Classic Gameplay**: Control the snake to eat food and grow longer.
- **Collision Detection**: The game ends if the snake collides with itself or the boundary.
- **Score Display**: Keep track of your score based on the amount of food eaten.
- **Multiple Difficulty Levels**: Choose from easy, medium, or hard difficulty levels to match your skill.

## How to Play

1. **Start the Game**: Run the game using the command `python main.py`.
2. **Control the Snake**: Use the arrow keys on your keyboard to change the direction of the snake.
3. **Eat Food**: Navigate the snake to the food items to eat them and grow longer.
4. **Avoid Collisions**: Do not let the snake collide with itself or the game boundaries.
5. **End of Game**: The game ends when a collision occurs. Your final score will be displayed.

## Game Controls

- **Arrow Keys**: Use the arrow keys (Up, Down, Left, Right) to control the direction of the snake.

## Difficulty Levels

The game offers three difficulty levels:

- **Easy**: Slow speed for beginners.
- **Medium**: Moderate speed for average players.
- **Hard**: Fast speed for experienced players.

You can set the difficulty level by modifying the `level` parameter in the `Difficulty` class within the `main.py` file.

## Scoring

- **Score Calculation**: Your score increases by 1 point for each food item eaten.
- **Display**: The current score is displayed on the top-left corner of the game screen.

Enjoy the game and challenge yourself to achieve the highest score possible!