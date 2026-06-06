'''
Main entry point for the interactive storytelling game. Initializes the game and starts the game loop.
'''
import pygame
from story_manager import StoryManager
from player import Player
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("Interactive Storytelling Game")
        self.clock = pygame.time.Clock()
        self.story_manager = StoryManager()
        self.player = Player()
        self.running = True
    def start(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    self.story_manager.make_choice(0, self.player)
                elif event.key == pygame.K_2:
                    self.story_manager.make_choice(1, self.player)
    def update(self):
        pass  # Update game state if necessary
    def render(self):
        self.screen.fill((0, 0, 0))
        current_node = self.story_manager.get_current_node()
        font = pygame.font.Font(None, 36)
        text_surface = font.render(current_node.text, True, (255, 255, 255))
        self.screen.blit(text_surface, (50, 50))
        for i, choice in enumerate(current_node.choices):
            if choice.is_available(self.player):
                choice_surface = font.render(f"{i+1}. {choice.text}", True, (255, 255, 255))
                self.screen.blit(choice_surface, (50, 100 + i * 40))
        pygame.display.flip()
if __name__ == "__main__":
    game = Game()
    game.start()