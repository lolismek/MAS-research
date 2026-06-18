'''
Tile map storage and helper methods for walls, floors, doors, chests, and monsters.
Out-of-bounds coordinates are treated safely as walls for collision checks.
'''
class TileMap:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = [[1 for _ in range(width)] for _ in range(height)]  # 1 = wall, 0 = floor
        self.start_x = 0
        self.start_y = 0
        self.door_x = width - 1
        self.door_y = height - 1
        self.chests = []
        self.monsters = {}
    def fill_walls(self):
        for y in range(self.height):
            for x in range(self.width):
                self.grid[y][x] = 1
    def in_bounds(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height
    def set_floor(self, x, y):
        if self.in_bounds(x, y):
            self.grid[y][x] = 0
    def is_wall(self, x, y):
        if not self.in_bounds(x, y):
            return True
        return self.grid[y][x] == 1
    def is_floor(self, x, y):
        if not self.in_bounds(x, y):
            return False
        return self.grid[y][x] == 0
    def is_door(self, x, y):
        return x == self.door_x and y == self.door_y
    def has_chest(self, x, y):
        return any(chest.x == x and chest.y == y for chest in self.chests)
    def pickup_chest(self, x, y):
        for i, chest in enumerate(self.chests):
            if chest.x == x and chest.y == y:
                self.chests.pop(i)
                return chest.heal
        return 0
    def has_monster(self, x, y):
        return (x, y) in self.monsters
    def get_monster(self, x, y):
        return self.monsters.get((x, y))
    def remove_monster(self, x, y):
        if (x, y) in self.monsters:
            del self.monsters[(x, y)]