'''
Represents objects that can be grabbed in the Gold Miner game.
'''
import pygame
class Object:
    def __init__(self, x, y, value, weight):
        self.position = [x, y]
        self.value = value
        self.weight = weight
        self.grabbed = False
    def is_within_reach(self, claw_position):
        # Logic to determine if the object is within reach of the claw
        return abs(claw_position[0] - self.position[0]) < 10
    def draw(self, screen):
        pygame.draw.circle(screen, (255, 215, 0), self.position, 10)