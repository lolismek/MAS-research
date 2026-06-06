'''
Paddle class to represent the player's paddle.
'''
import pygame
from constants import *
class Paddle:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, PADDLE_WIDTH, PADDLE_HEIGHT)
    def move_up(self):
        if self.rect.top > 0:
            self.rect.y -= PADDLE_SPEED
    def move_down(self):
        if self.rect.bottom < SCREEN_HEIGHT:
            self.rect.y += PADDLE_SPEED
    def draw(self, screen):
        pygame.draw.rect(screen, WHITE, self.rect)