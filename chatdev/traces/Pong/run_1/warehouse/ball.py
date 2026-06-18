'''
Ball entity for Pong.
Handles movement, speed scaling, direction reset, and rendering.
'''
import random
import pygame
class Ball:
    def __init__(self, x, y, radius, vel_x, vel_y, color):
        self.start_x = x
        self.start_y = y
        self.radius = radius
        self.base_vel_x = vel_x
        self.base_vel_y = vel_y
        self.color = color
        self.x = x
        self.y = y
        self.vel_x = vel_x
        self.vel_y = vel_y
    def reset(self, x, y, direction=1):
        self.x = x
        self.y = y
        self.vel_x = abs(self.base_vel_x) * direction
        self.vel_y = self.base_vel_y * random.choice([-1, 1])
    def update(self):
        self.x += self.vel_x
        self.y += self.vel_y
    def increase_speed(self):
        self.vel_x *= 1.05
        self.vel_y *= 1.05
    def apply_paddle_bounce(self, paddle):
        paddle_center = paddle.y + paddle.height / 2
        ball_center = self.y
        offset = (ball_center - paddle_center) / (paddle.height / 2)
        self.vel_y = self.base_vel_y * offset * 2.0
        if self.vel_y == 0:
            self.vel_y = random.choice([-1, 1]) * self.base_vel_y
    def get_rect(self):
        return pygame.Rect(
            int(self.x - self.radius),
            int(self.y - self.radius),
            self.radius * 2,
            self.radius * 2,
        )
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)