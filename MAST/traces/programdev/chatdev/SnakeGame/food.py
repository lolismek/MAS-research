'''
Food class to manage food properties and behavior.
'''
import pygame
import random
class Food:
    def __init__(self):
        self.position = (random.randrange(1, 60) * 10, random.randrange(1, 40) * 10)
    def spawn(self):
        self.position = (random.randrange(1, 60) * 10, random.randrange(1, 40) * 10)
    def draw(self, screen):
        pygame.draw.rect(screen, (255, 0, 0), pygame.Rect(self.position[0], self.position[1], 10, 10))