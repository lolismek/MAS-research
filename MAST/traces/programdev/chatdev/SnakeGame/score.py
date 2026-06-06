'''
Score class to manage and display the score.
'''
import pygame
class Score:
    def __init__(self):
        self.score = 0
        self.font = pygame.font.SysFont('Arial', 25)
    def increase(self):
        self.score += 1
    def display(self, screen):
        score_surface = self.font.render(f'Score: {self.score}', True, (255, 255, 255))
        screen.blit(score_surface, (10, 10))