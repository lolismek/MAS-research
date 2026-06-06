'''
Defines the Player class for the roguelike game.
'''
import random
class Player:
    def __init__(self, start_position):
        self.x, self.y = start_position
        self.hp = 100
        self.attack_power = 10
    def move(self, direction, game_map):
        if direction == 'up' and game_map.is_valid_move(self.x, self.y - 1):
            self.y -= 1
        elif direction == 'down' and game_map.is_valid_move(self.x, self.y + 1):
            self.y += 1
        elif direction == 'left' and game_map.is_valid_move(self.x - 1, self.y):
            self.x -= 1
        elif direction == 'right' and game_map.is_valid_move(self.x + 1, self.y):
            self.x += 1
    def combat(self, monster):
        self.hp -= monster.attack_power
        monster.hp -= self.attack_power
    def collect_treasure(self):
        self.hp += random.randint(20, 30)