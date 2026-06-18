'''
Entity classes for the player, monsters, and treasure chests.
'''
from dataclasses import dataclass
@dataclass
class Player:
    x: int
    y: int
    hp: int = 100
@dataclass
class Monster:
    x: int
    y: int
    hp: int
@dataclass
class Chest:
    x: int
    y: int
    heal: int