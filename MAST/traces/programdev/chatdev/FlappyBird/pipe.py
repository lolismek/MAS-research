'''
Pipe class to manage the pipes' movement and collision detection.
'''
import pygame
class Pipe:
    def __init__(self, gap_y):
        self.x = 400
        self.gap_y = gap_y
        self.width = 50
        self.gap_height = 150
        self.speed = 3
    def update(self, score):
        self.x -= self.speed + score // 10  # Increase speed as score increases
    def off_screen(self):
        return self.x < -self.width
    def draw(self, screen):
        pygame.draw.rect(screen, (0, 255, 0), (self.x, 0, self.width, self.gap_y))
        pygame.draw.rect(screen, (0, 255, 0), (self.x, self.gap_y + self.gap_height, self.width, 600))