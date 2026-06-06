'''
Ball class to represent the ball in the game.
'''
import pygame
from constants import *
class Ball:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, BALL_SIZE, BALL_SIZE)
        self.dx = BALL_SPEED
        self.dy = BALL_SPEED
    def move(self, paddle1, paddle2, scoreboard):
        self.rect.x += self.dx
        self.rect.y += self.dy
        # Bounce off top and bottom
        if self.rect.top <= 0 or self.rect.bottom >= SCREEN_HEIGHT:
            self.dy = -self.dy
        # Bounce off paddles
        if self.rect.colliderect(paddle1.rect) or self.rect.colliderect(paddle2.rect):
            self.dx = -self.dx
        # Check for scoring
        if self.rect.left <= 0:
            scoreboard.update_score(2)
            self.reset()
        elif self.rect.right >= SCREEN_WIDTH:
            scoreboard.update_score(1)
            self.reset()
    def reset(self):
        self.rect.x = SCREEN_WIDTH // 2
        self.rect.y = SCREEN_HEIGHT // 2
        self.dx = -self.dx
    def draw(self, screen):
        pygame.draw.ellipse(screen, WHITE, self.rect)