'''
Handles the game logic for Minesweeper, including board generation and game state updates.
'''
import random
class MinesweeperGame:
    def __init__(self, rows, cols, mines):
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.board = []
        self.revealed = []
        self.flags = []
        self.game_over = False
        self.generate_board()
    def generate_board(self):
        self.board = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.revealed = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        self.flags = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        # Place mines
        mine_positions = set()
        while len(mine_positions) < self.mines:
            r = random.randint(0, self.rows - 1)
            c = random.randint(0, self.cols - 1)
            mine_positions.add((r, c))
        for r, c in mine_positions:
            self.board[r][c] = -1
        # Calculate numbers
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1:
                    continue
                self.board[r][c] = self.count_adjacent_mines(r, c)
    def count_adjacent_mines(self, row, col):
        count = 0
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                r, c = row + dr, col + dc
                if 0 <= r < self.rows and 0 <= c < self.cols and self.board[r][c] == -1:
                    count += 1
        return count
    def reveal_cell(self, row, col):
        if self.game_over or self.revealed[row][col] or self.flags[row][col]:
            return
        self.revealed[row][col] = True
        if self.board[row][col] == -1:
            self.game_over = True
            return
        if self.board[row][col] == 0:
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    r, c = row + dr, col + dc
                    if 0 <= r < self.rows and 0 <= c < self.cols:
                        self.reveal_cell(r, c)
    def flag_cell(self, row, col):
        if self.revealed[row][col]:
            return
        self.flags[row][col] = not self.flags[row][col]
    def check_win(self):
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] != -1 and not self.revealed[r][c]:
                    return False
        return True