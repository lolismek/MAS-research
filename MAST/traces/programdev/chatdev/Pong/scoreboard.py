'''
Scoreboard class to keep track of the players' scores.
'''
import pygame
from constants import *
class Scoreboard:
    def __init__(self):
        self.score1 = 0
        self.score2 = 0
        self.font = pygame.font.Font(None, 74)
    def update_score(self, player):
        if player == 1:
            self.score1 += 1
        else:
            self.score2 += 1
    def check_winner(self):
        if self.score1 >= WINNING_SCORE:
            return 1
        elif self.score2 >= WINNING_SCORE:
            return 2
        return None
    def draw(self, screen):
        score_text = f"{self.score1} - {self.score2}"
        text = self.font.render(score_text, True, WHITE)
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 10))