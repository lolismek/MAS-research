'''
Utility functions for the roguelike game.
'''
import random
from collections import deque
def random_position(width, height):
    return random.randint(0, width - 1), random.randint(0, height - 1)
def find_path(start, end, grid):
    width = len(grid[0])
    height = len(grid)
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    queue = deque([start])
    visited = set()
    visited.add(start)
    while queue:
        current = queue.popleft()
        if current == end:
            return True
        for direction in directions:
            next_x, next_y = current[0] + direction[0], current[1] + direction[1]
            if 0 <= next_x < width and 0 <= next_y < height and grid[next_y][next_x] == 'floor' and (next_x, next_y) not in visited:
                queue.append((next_x, next_y))
                visited.add((next_x, next_y))
    return False