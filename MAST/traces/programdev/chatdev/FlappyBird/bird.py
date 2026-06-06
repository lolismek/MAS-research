'''
Bird class to manage the bird's movement and collision detection.
'''
import pygame
class Bird:
    def __init__(self):
        self.x = 50
        self.y = 300
        self.velocity = 0
        self.gravity = 0.5
        self.flap_strength = -10
        self.radius = 15
    def flap(self):
        self.velocity = self.flap_strength
    def update(self, game):
        self.velocity += self.gravity
        self.y += self.velocity
        if self.y > 585:  # Ground collision
            self.y = 585
            self.velocity = 0
            game.game_over()  # End the game when the bird hits the ground
    def draw(self, screen):
        pygame.draw.circle(screen, (255, 255, 0), (self.x, int(self.y)), self.radius)