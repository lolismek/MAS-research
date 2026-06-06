'''
Manages the player's score and updates it when lines are cleared.
'''
import pygame
from constants import FONT_SIZE, SCREEN_WIDTH
class Score:
    def __init__(self):
        self.score = 0
        self.font = pygame.font.Font(None, FONT_SIZE)
    def add_score(self, lines_cleared):
        self.score += lines_cleared * 100  # Example scoring: 100 points per line
    def reset(self):
        self.score = 0
    def draw(self, screen):
        score_text = self.font.render(f"Score: {self.score}", True, (255, 255, 255))
        screen.blit(score_text, (SCREEN_WIDTH - 150, 20))