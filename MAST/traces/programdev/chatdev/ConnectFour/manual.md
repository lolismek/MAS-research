# Connect Four Game User Manual

Welcome to the Connect Four Game! This manual will guide you through the installation, setup, and gameplay of the Connect Four application developed using Python and Tkinter.

## Introduction

Connect Four is a classic two-player connection game in which the players first choose a color and then take turns dropping colored discs into a seven-column, six-row grid. The pieces fall straight down, occupying the lowest available space within the column. The objective of the game is to be the first to form a horizontal, vertical, or diagonal line of four of one's own discs.

## Main Features

- **Interactive Gameplay**: Two players can play against each other on the same device.
- **Graphical User Interface**: The game features a simple and intuitive GUI built with Tkinter.
- **Real-time Updates**: The board updates in real-time as players make their moves.
- **Win and Draw Detection**: The game automatically detects and announces a win or a draw.
- **Replay Option**: Players can choose to play again after a game ends.

## Installation

### Prerequisites

- **Python**: Ensure that Python is installed on your system. You can download it from [python.org](https://www.python.org/downloads/).
- **Tkinter**: Tkinter is included with standard Python installations, so no additional installation is required.

### Installation Steps

1. **Clone the Repository**: Clone the project repository to your local machine using the following command:
   ```bash
   git clone <repository-url>
   ```
   Replace `<repository-url>` with the actual URL of the repository.

2. **Navigate to the Project Directory**: Change to the project directory:
   ```bash
   cd <project-directory>
   ```

3. **Run the Game**: Execute the main script to start the game:
   ```bash
   python main.py
   ```

## How to Play

1. **Start the Game**: Run the `main.py` script to launch the game window.

2. **Choose a Column**: Players take turns clicking on the buttons at the top of each column to drop their discs. The current player is indicated by the color of the disc (Red or Yellow).

3. **Objective**: The goal is to connect four of your discs in a row, either horizontally, vertically, or diagonally.

4. **Winning and Drawing**: The game will automatically detect and announce a winner when a player connects four discs. If the board fills up without a winner, the game will declare a draw.

5. **Replay**: After a game ends, a prompt will appear asking if you want to play again. Choose 'Yes' to restart the game or 'No' to exit.

## Troubleshooting

- **Tkinter Errors**: If you encounter issues related to Tkinter, ensure that your Python installation includes Tkinter. You may need to reinstall Python with Tkinter support.

- **Python Errors**: Ensure that you are using a compatible version of Python (preferably Python 3.x).

## Support

For further assistance, please contact our support team at support@chatdev.com.

Enjoy playing Connect Four!