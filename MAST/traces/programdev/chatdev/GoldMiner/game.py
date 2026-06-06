'''
Manages the game loop, events, updates, and rendering for the Gold Miner game.
'''
import pygame
from claw import Claw
from level import Level
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("Gold Miner")
        self.clock = pygame.time.Clock()
        self.running = True
        self.claw = Claw()
        self.levels = self.create_levels()
        self.current_level_index = 0
        self.current_level = self.levels[self.current_level_index]
    def create_levels(self):
        # Create multiple levels with increasing difficulty
        return [
            Level(minimum_gold_value=300, time_limit=60, objects=[
                (200, 500, 100, 10),
                (600, 500, 200, 20)
            ]),
            Level(minimum_gold_value=500, time_limit=50, objects=[
                (150, 500, 150, 15),
                (400, 500, 250, 25),
                (650, 500, 100, 10)
            ]),
            Level(minimum_gold_value=700, time_limit=40, objects=[
                (100, 500, 200, 20),
                (300, 500, 300, 30),
                (500, 500, 150, 15),
                (700, 500, 100, 10)
            ])
        ]
    def run(self):
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
                if event.key == pygame.K_SPACE:
                    self.claw.grab(self.current_level.objects)
    def update(self):
        self.claw.move()
        self.current_level.current_time += self.clock.get_time() / 1000  # Convert milliseconds to seconds
        if self.current_level.check_completion():
            self.advance_level()
    def render(self):
        self.screen.fill((0, 0, 0))
        self.claw.draw(self.screen)
        self.current_level.draw(self.screen)
        pygame.display.flip()
    def advance_level(self):
        self.current_level_index += 1
        if self.current_level_index < len(self.levels):
            self.current_level = self.levels[self.current_level_index]
        else:
            print("Congratulations! You've completed all levels!")
            self.running = False