'''
Entity classes for the simplified Space Invaders game.
'''
try:
    import pygame
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "pygame is required to run this game. Please install it with: pip install pygame"
    ) from exc
from settings import (
    ALIEN_HEIGHT,
    ALIEN_WIDTH,
    BULLET_HEIGHT,
    BULLET_SPEED,
    BULLET_WIDTH,
    PLAYER_FIRE_COOLDOWN_MS,
    PLAYER_HEIGHT,
    PLAYER_SPEED,
    PLAYER_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
class Player:
    '''Player-controlled ship at the bottom of the screen.'''
    def __init__(self):
        self.rect = pygame.Rect(
            (SCREEN_WIDTH - PLAYER_WIDTH) // 2,
            SCREEN_HEIGHT - 60,
            PLAYER_WIDTH,
            PLAYER_HEIGHT,
        )
        self.speed = PLAYER_SPEED
        self.last_shot_time = 0
    def move_left(self):
        '''Move the player left, clamped to screen bounds.'''
        self.rect.x = max(0, self.rect.x - self.speed)
    def move_right(self):
        '''Move the player right, clamped to screen bounds.'''
        self.rect.x = min(SCREEN_WIDTH - self.rect.width, self.rect.x + self.speed)
    def can_fire(self):
        '''Return True if cooldown allows firing.'''
        return pygame.time.get_ticks() - self.last_shot_time >= PLAYER_FIRE_COOLDOWN_MS
    def fire(self):
        '''Create and return a bullet if possible.'''
        if not self.can_fire():
            return None
        self.last_shot_time = pygame.time.get_ticks()
        bullet_x = self.rect.centerx - BULLET_WIDTH // 2
        bullet_y = self.rect.top - BULLET_HEIGHT
        return Bullet(bullet_x, bullet_y)
    def draw(self, surface, color):
        '''Draw the player ship.'''
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
class Bullet:
    '''Projectile fired by the player.'''
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, BULLET_WIDTH, BULLET_HEIGHT)
        self.speed = BULLET_SPEED
    def update(self):
        '''Move bullet upward.'''
        self.rect.y -= self.speed
    def off_screen(self):
        '''Check whether bullet left the screen.'''
        return self.rect.bottom < 0
    def draw(self, surface, color):
        '''Draw the bullet.'''
        pygame.draw.rect(surface, color, self.rect)
class Alien:
    '''Single alien in the formation.'''
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, ALIEN_WIDTH, ALIEN_HEIGHT)
    def draw(self, surface, color):
        '''Draw the alien.'''
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        eye_radius = max(2, self.rect.width // 10)
        pygame.draw.circle(
            surface,
            (20, 20, 20),
            (self.rect.centerx - 8, self.rect.centery - 2),
            eye_radius,
        )
        pygame.draw.circle(
            surface,
            (20, 20, 20),
            (self.rect.centerx + 8, self.rect.centery - 2),
            eye_radius,
        )