'''
Defines the Map class for the roguelike game.
'''
import random
from utils import find_path, random_position, generate_maze
from monster import Monster
class Map:
    def __init__(self):
        self.width = 80
        self.height = 80
        self.grid = [['floor' for _ in range(self.width)] for _ in range(self.height)]
        self.start_position = (0, 0)
        self.door_position = (79, 79)
        self.place_walls()
        self.ensure_valid_path()
    def place_walls(self):
        # Use a maze generation algorithm to ensure a valid path
        self.grid = generate_maze(self.width, self.height, self.start_position, self.door_position)
    def ensure_valid_path(self):
        # This method is now redundant as the maze generation ensures a valid path
        pass
    def is_valid_move(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x] == 'floor'
        return False
    def place_monsters(self):
        monsters = []
        for _ in range(10):  # Place 10 monsters
            x, y = random_position(self.width, self.height)
            while self.grid[y][x] != 'floor' or (x, y) == self.start_position or (x, y) == self.door_position:
                x, y = random_position(self.width, self.height)
            monsters.append(Monster((x, y), hp=20, attack_power=5))
        return monsters
    def place_treasure_chests(self):
        chests = []
        for _ in range(5):  # Place 5 treasure chests
            x, y = random_position(self.width, self.height)
            while self.grid[y][x] != 'floor' or (x, y) == self.start_position or (x, y) == self.door_position:
                x, y = random_position(self.width, self.height)
            chests.append((x, y))
        return chests