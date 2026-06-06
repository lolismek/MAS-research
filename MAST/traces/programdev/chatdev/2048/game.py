'''
Game logic for the 2048 game, including state management and tile operations.
'''
import random
class Game:
    def __init__(self):
        self.grid = [[0] * 4 for _ in range(4)]
        self.score = 0
        self.reset()
    def reset(self):
        self.grid = [[0] * 4 for _ in range(4)]
        self.score = 0
        self.add_new_tile()
        self.add_new_tile()
    def move(self, direction):
        if direction in ['up', 'down', 'left', 'right']:
            moved = False
            original_grid = [row[:] for row in self.grid]  # Copy the grid
            for i in range(4):
                if direction in ['left', 'right']:
                    row = self.grid[i]
                    if direction == 'right':
                        row.reverse()
                    merged, score = self.merge(row)
                    if direction == 'right':
                        merged.reverse()
                    self.grid[i] = merged
                    self.score += score
                else:
                    col = [self.grid[j][i] for j in range(4)]
                    if direction == 'down':
                        col.reverse()
                    merged, score = self.merge(col)
                    if direction == 'down':
                        merged.reverse()
                    for j in range(4):
                        self.grid[j][i] = merged[j]
                    self.score += score
            if self.grid != original_grid:  # Compare the grid before and after the move
                moved = True
            if moved:
                self.add_new_tile()
    def merge(self, line):
        merged = [i for i in line if i != 0]
        score = 0
        i = 0
        while i < len(merged) - 1:
            if merged[i] == merged[i + 1]:
                merged[i] *= 2
                score += merged[i]
                merged[i + 1] = 0
                i += 1  # Skip the next tile since it has been merged
            i += 1
        merged = [i for i in merged if i != 0]
        return merged + [0] * (4 - len(merged)), score
    def add_new_tile(self):
        empty_cells = [(i, j) for i in range(4) for j in range(4) if self.grid[i][j] == 0]
        if empty_cells:
            i, j = random.choice(empty_cells)
            self.grid[i][j] = random.choice([2, 4])
    def is_game_over(self):
        if any(0 in row for row in self.grid):
            return False
        for i in range(4):
            for j in range(4):
                if j < 3 and self.grid[i][j] == self.grid[i][j + 1]:
                    return False
                if i < 3 and self.grid[i][j] == self.grid[i + 1][j]:
                    return False
        return True
    def get_highest_tile(self):
        return max(max(row) for row in self.grid)