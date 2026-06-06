'''
Score class to manage the player's score.
'''
import pygame
class Score:
    def __init__(self):
        self.score = 0
        self.font = pygame.font.Font(None, 36)
    def increment(self):
        self.score += 1
    def draw(self, screen):
        score_text = self.font.render(f"Score: {self.score}", True, (255, 255, 255))
        screen.blit(score_text, (10, 10))