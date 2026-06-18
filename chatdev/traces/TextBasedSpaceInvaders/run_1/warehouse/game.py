'''
Main game logic for the simplified Space Invaders game.
'''
import sys
try:
    import pygame
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "pygame is required to run this game. Please install it with: pip install pygame"
    ) from exc
from entities import Alien, Player
from settings import (
    ALIEN_COLS,
    ALIEN_DROP_DISTANCE,
    ALIEN_EDGE_PADDING,
    ALIEN_HEIGHT,
    ALIEN_MOVE_DELAY_MS,
    ALIEN_ROWS,
    ALIEN_START_X,
    ALIEN_START_Y,
    ALIEN_WIDTH,
    ALIEN_X_GAP,
    ALIEN_Y_GAP,
    ALIEN_BOTTOM_DANGER_LINE,
    BLACK,
    BLUE,
    END_TEXT_SIZE,
    FPS,
    GREEN,
    HUD_MARGIN,
    INFO_TEXT_SIZE,
    PLAYER_LIVES,
    RED,
    RESPAWN_DELAY_MS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SCORE_PER_ALIEN,
    WHITE,
    YELLOW,
)
class Game:
    '''Space Invaders game controller.'''
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Simplified Space Invaders")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_hud = pygame.font.SysFont("arial", INFO_TEXT_SIZE, bold=True)
        self.font_end = pygame.font.SysFont("arial", END_TEXT_SIZE, bold=True)
        self.font_small = pygame.font.SysFont("arial", 20)
        self.player = Player()
        self.bullets = []
        self.aliens = []
        self.score = 0
        self.lives = PLAYER_LIVES
        self.game_over = False
        self.win = False
        self.alien_direction = 1
        self.last_alien_move = pygame.time.get_ticks()
        self.respawn_pending = False
        self.respawn_time = 0
        self.pause_aliens = False
        self.create_alien_fleet()
    def create_alien_fleet(self):
        '''Generate a grid of aliens.'''
        self.aliens.clear()
        for row in range(ALIEN_ROWS):
            for col in range(ALIEN_COLS):
                x = ALIEN_START_X + col * (ALIEN_WIDTH + ALIEN_X_GAP)
                y = ALIEN_START_Y + row * (ALIEN_HEIGHT + ALIEN_Y_GAP)
                self.aliens.append(Alien(x, y))
    def run(self):
        '''Run the main loop.'''
        while True:
            self.handle_events()
            if not self.game_over:
                self.update()
            self.draw()
            self.clock.tick(FPS)
    def handle_events(self):
        '''Process user and window events.'''
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and not self.game_over and not self.respawn_pending:
                    bullet = self.player.fire()
                    if bullet:
                        self.bullets.append(bullet)
                if event.key == pygame.K_r and self.game_over:
                    self.restart()
    def restart(self):
        '''Reset game state after a win or loss.'''
        self.player = Player()
        self.bullets = []
        self.score = 0
        self.lives = PLAYER_LIVES
        self.game_over = False
        self.win = False
        self.alien_direction = 1
        self.last_alien_move = pygame.time.get_ticks()
        self.respawn_pending = False
        self.respawn_time = 0
        self.pause_aliens = False
        self.create_alien_fleet()
    def update(self):
        '''Update game objects and check win/lose conditions.'''
        now = pygame.time.get_ticks()
        if self.respawn_pending:
            if now >= self.respawn_time:
                self.respawn_pending = False
                self.pause_aliens = False
                self.player = Player()
                self.bullets.clear()
                self.create_alien_fleet()
                self.alien_direction = 1
                self.last_alien_move = now
            else:
                return
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player.move_left()
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player.move_right()
        self.update_bullets()
        if not self.pause_aliens:
            self.update_aliens()
        self.check_player_collision()
        self.check_alien_reach_bottom()
        if not self.aliens:
            self.game_over = True
            self.win = True
    def update_bullets(self):
        '''Move bullets and resolve collisions.'''
        for bullet in self.bullets[:]:
            bullet.update()
            if bullet.off_screen():
                self.bullets.remove(bullet)
        for bullet in self.bullets[:]:
            hit_alien = None
            for alien in self.aliens:
                if bullet.rect.colliderect(alien.rect):
                    hit_alien = alien
                    break
            if hit_alien:
                self.aliens.remove(hit_alien)
                if bullet in self.bullets:
                    self.bullets.remove(bullet)
                self.score += SCORE_PER_ALIEN
    def update_aliens(self):
        '''Move alien formation and bounce at screen edges.'''
        now = pygame.time.get_ticks()
        if now - self.last_alien_move < ALIEN_MOVE_DELAY_MS:
            return
        self.last_alien_move = now
        move_x = 12 * self.alien_direction
        edge_hit = False
        for alien in self.aliens:
            alien.rect.x += move_x
            if (
                alien.rect.right >= SCREEN_WIDTH - ALIEN_EDGE_PADDING
                or alien.rect.left <= ALIEN_EDGE_PADDING
            ):
                edge_hit = True
        if edge_hit:
            self.alien_direction *= -1
            for alien in self.aliens:
                alien.rect.y += ALIEN_DROP_DISTANCE
    def check_player_collision(self):
        '''Lose a life if an alien touches the player.'''
        if self.respawn_pending:
            return
        for alien in self.aliens:
            if alien.rect.colliderect(self.player.rect):
                self.lose_life()
                return
    def check_alien_reach_bottom(self):
        '''Lose a life if any alien reaches the fixed danger line.'''
        if self.respawn_pending:
            return
        for alien in self.aliens:
            if alien.rect.bottom >= ALIEN_BOTTOM_DANGER_LINE:
                self.lose_life()
                return
    def lose_life(self):
        '''Handle life loss and respawn logic.'''
        if self.respawn_pending or self.game_over:
            return
        self.lives -= 1
        self.bullets.clear()
        if self.lives <= 0:
            self.game_over = True
            self.win = False
            return
        self.respawn_pending = True
        self.pause_aliens = True
        self.respawn_time = pygame.time.get_ticks() + RESPAWN_DELAY_MS
        # Give the player a fair reset by moving aliens back to a safe starting state.
        self.reset_alien_positions()
    def reset_alien_positions(self):
        '''Reposition aliens higher if they are too close to the bottom.'''
        if not self.aliens:
            return
        lowest_bottom = max(alien.rect.bottom for alien in self.aliens)
        if lowest_bottom < ALIEN_BOTTOM_DANGER_LINE:
            return
        # Rebuild the fleet in the original formation to prevent unfair rapid life loss.
        self.create_alien_fleet()
        self.alien_direction = 1
    def draw(self):
        '''Render all game elements.'''
        self.screen.fill(BLACK)
        for alien in self.aliens:
            alien.draw(self.screen, GREEN)
        for bullet in self.bullets:
            bullet.draw(self.screen, YELLOW)
        self.player.draw(self.screen, BLUE)
        self.draw_hud()
        if self.respawn_pending:
            self.draw_respawn_message()
        if self.game_over:
            self.draw_end_screen()
        pygame.display.flip()
    def draw_hud(self):
        '''Draw score and lives.'''
        score_text = self.font_hud.render(f"Score: {self.score}", True, WHITE)
        lives_text = self.font_hud.render(f"Lives: {self.lives}", True, WHITE)
        aliens_text = self.font_hud.render(f"Aliens: {len(self.aliens)}", True, WHITE)
        self.screen.blit(score_text, (HUD_MARGIN, HUD_MARGIN))
        self.screen.blit(lives_text, (HUD_MARGIN, HUD_MARGIN + 28))
        self.screen.blit(aliens_text, (HUD_MARGIN, HUD_MARGIN + 56))
    def draw_respawn_message(self):
        '''Show a short respawn notice after losing a life.'''
        msg = self.font_small.render("Life lost! Prepare for the next wave...", True, WHITE)
        rect = msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(msg, rect)
    def draw_end_screen(self):
        '''Overlay win/lose message and restart prompt.'''
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        title = "YOU WIN!" if self.win else "GAME OVER"
        title_color = GREEN if self.win else RED
        title_surface = self.font_end.render(title, True, title_color)
        prompt_surface = self.font_small.render(
            "Press R to restart or close the window to exit.",
            True,
            WHITE,
        )
        title_rect = title_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 25))
        prompt_rect = prompt_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 25))
        self.screen.blit(title_surface, title_rect)
        self.screen.blit(prompt_surface, prompt_rect)