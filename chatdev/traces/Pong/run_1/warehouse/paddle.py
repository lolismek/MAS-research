'''
Paddle entity for Pong.
Handles movement, boundary clamping, and rendering.
'''
import pygame
class Paddle:
    def __init__(self, x, y, width, height, speed, color):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.speed = speed
        self.color = color
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)
    def move_up(self, top_limit):
        self.y = max(top_limit, self.y - self.speed)
    def move_down(self, bottom_limit):
        self.y = min(bottom_limit - self.height, self.y + self.speed)
    def reset(self, x, y):
        self.x = x
        self.y = y
    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect(), border_radius=6)