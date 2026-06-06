'''
Game class to manage the game loop, initialize game components, and handle game states.
'''
import pygame
from bird import Bird
from pipe import Pipe
from score import Score
from utils import check_collision, generate_random_gap
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((400, 600))
        self.clock = pygame.time.Clock()
        self.bird = Bird()
        self.pipes = []
        self.score = Score()
        self.running = True
        self.pipe_timer = 0
    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.bird.flap()
    def update(self):
        self.bird.update(self)  # Pass the game instance to the bird
        self.pipe_timer += 1
        if self.pipe_timer > 90:
            self.pipes.append(Pipe(generate_random_gap(self.score.score)))
            self.pipe_timer = 0
        for pipe in self.pipes:
            pipe.update(self.score.score)
            if check_collision(self.bird, pipe):
                self.running = False
            if pipe.off_screen():
                self.pipes.remove(pipe)
                self.score.increment()
    def draw(self):
        self.screen.fill((135, 206, 235))  # Sky blue background
        self.bird.draw(self.screen)
        for pipe in self.pipes:
            pipe.draw(self.screen)
        self.score.draw(self.screen)
        pygame.display.flip()
    def game_over(self):
        self.running = False