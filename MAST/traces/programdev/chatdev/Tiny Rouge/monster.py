'''
Defines the Monster class for the roguelike game.
'''
class Monster:
    def __init__(self, position, hp, attack_power):
        self.x, self.y = position
        self.hp = hp
        self.attack_power = attack_power