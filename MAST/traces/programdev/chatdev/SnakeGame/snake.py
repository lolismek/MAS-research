'''
Snake class to manage snake properties and behavior.
'''
import pygame
class Snake:
    def __init__(self):
        self.body = [(100, 50), (90, 50), (80, 50)]
        self.direction = 'RIGHT'
        self.change_to = self.direction
    def change_direction(self, direction):
        if direction == 'UP' and not self.direction == 'DOWN':
            self.direction = 'UP'
        if direction == 'DOWN' and not self.direction == 'UP':
            self.direction = 'DOWN'
        if direction == 'LEFT' and not self.direction == 'RIGHT':
            self.direction = 'LEFT'
        if direction == 'RIGHT' and not self.direction == 'LEFT':
            self.direction = 'RIGHT'
    def move(self):
        x, y = self.body[0]
        if self.direction == 'UP':
            y -= 10
        if self.direction == 'DOWN':
            y += 10
        if self.direction == 'LEFT':
            x -= 10
        if self.direction == 'RIGHT':
            x += 10
        self.body = [(x, y)] + self.body[:-1]
    def grow(self):
        self.body.append(self.body[-1])
    def check_collision(self):
        x, y = self.body[0]
        if x < 0 or x >= 600 or y < 0 or y >= 400:
            return True
        if (x, y) in self.body[1:]:
            return True
        return False
    def head_position(self):
        return self.body[0]
    def draw(self, screen):
        for segment in self.body:
            pygame.draw.rect(screen, (0, 255, 0), pygame.Rect(segment[0], segment[1], 10, 10))