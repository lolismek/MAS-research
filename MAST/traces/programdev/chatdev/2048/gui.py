'''
Graphical user interface for the 2048 game using Pygame.
'''
import pygame
import sys
class GUI:
    def __init__(self, game):
        self.game = game
        self.screen = pygame.display.set_mode((400, 500))
        pygame.display.set_caption('2048')
        self.font = pygame.font.Font(None, 50)
        self.colors = {
            0: (205, 193, 180),
            2: (238, 228, 218),
            4: (237, 224, 200),
            8: (242, 177, 121),
            16: (245, 149, 99),
            32: (246, 124, 95),
            64: (246, 94, 59),
            128: (237, 207, 114),
            256: (237, 204, 97),
            512: (237, 200, 80),
            1024: (237, 197, 63),
            2048: (237, 194, 46),
        }
    def draw_grid(self):
        self.screen.fill((187, 173, 160))
        for i in range(4):
            for j in range(4):
                value = self.game.grid[i][j]
                color = self.colors.get(value, (60, 58, 50))
                pygame.draw.rect(self.screen, color, (j * 100 + 10, i * 100 + 10, 90, 90))
                if value != 0:
                    text = self.font.render(str(value), True, (0, 0, 0))
                    text_rect = text.get_rect(center=(j * 100 + 55, i * 100 + 55))
                    self.screen.blit(text, text_rect)
    def draw_score(self):
        score_text = self.font.render(f'Score: {self.game.score}', True, (255, 255, 255))
        self.screen.blit(score_text, (10, 410))
        highest_tile_text = self.font.render(f'Highest Tile: {self.game.get_highest_tile()}', True, (255, 255, 255))
        self.screen.blit(highest_tile_text, (10, 460))
    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.game.move('up')
            elif event.key == pygame.K_DOWN:
                self.game.move('down')
            elif event.key == pygame.K_LEFT:
                self.game.move('left')
            elif event.key == pygame.K_RIGHT:
                self.game.move('right')
    def update(self):
        self.draw_grid()
        self.draw_score()