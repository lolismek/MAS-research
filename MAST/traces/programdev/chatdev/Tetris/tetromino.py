'''
Represents a Tetromino piece and handles its movement and rotation.
'''
import pygame
from constants import TETROMINO_SHAPES, BLOCK_SIZE, BOARD_WIDTH
import random
class Tetromino:
    def __init__(self):
        self.shape = random.choice(TETROMINO_SHAPES)
        self.position = [BOARD_WIDTH // 2 - len(self.shape[0]) // 2, 0]
    def rotate(self):
        self.shape = [list(row) for row in zip(*self.shape[::-1])]
    def move(self, direction):
        if direction == "left":
            self.position[0] -= 1
        elif direction == "right":
            self.position[0] += 1
        elif direction == "down":
            self.position[1] += 1
        elif direction == "up":
            self.position[1] -= 1
    def draw(self, screen):
        for y, row in enumerate(self.shape):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(screen, (255, 255, 255), 
                                     ((self.position[0] + x) * BLOCK_SIZE, 
                                      (self.position[1] + y) * BLOCK_SIZE, 
                                      BLOCK_SIZE, BLOCK_SIZE))