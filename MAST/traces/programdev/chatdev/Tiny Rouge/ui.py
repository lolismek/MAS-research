'''
Defines the UI class for rendering the game state.
'''
import pygame
class UI:
    def __init__(self, screen, player):
        self.screen = screen
        self.player = player
    def draw(self, game_map, monsters, treasure_chests):
        for y in range(game_map.height):
            for x in range(game_map.width):
                if game_map.grid[y][x] == 'wall':
                    color = (100, 100, 100)
                else:
                    color = (200, 200, 200)
                pygame.draw.rect(self.screen, color, (x * 10, y * 10, 10, 10))
        pygame.draw.rect(self.screen, (0, 255, 0), (self.player.x * 10, self.player.y * 10, 10, 10))
        for monster in monsters:
            pygame.draw.rect(self.screen, (255, 0, 0), (monster.x * 10, monster.y * 10, 10, 10))
        for chest in treasure_chests:
            pygame.draw.rect(self.screen, (255, 215, 0), (chest[0] * 10, chest[1] * 10, 10, 10))
        self.draw_ui()
    def draw_ui(self):
        font = pygame.font.SysFont(None, 24)
        hp_text = font.render(f'HP: {self.player.hp}', True, (255, 255, 255))
        self.screen.blit(hp_text, (10, 10))