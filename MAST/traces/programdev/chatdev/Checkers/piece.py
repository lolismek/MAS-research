'''
Piece class to represent individual pieces on the board.
'''
import pygame
from utils import position_to_coordinates
class Piece:
    def __init__(self, color, position):
        self.color = color
        self.position = position
        self.king = False
    def draw(self, screen):
        x, y = position_to_coordinates(self.position)
        radius = 40
        pygame.draw.circle(screen, (255, 0, 0) if self.color == 'black' else (0, 0, 255), (x, y), radius)
        if self.king:
            pygame.draw.circle(screen, (255, 215, 0), (x, y), radius // 2)