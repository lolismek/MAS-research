'''
Main game logic for Pong.
Handles input, collisions, scoring, serving, rendering, and win conditions.
'''
import sys
import pygame
from paddle import Paddle
from ball import Ball
class PongGame:
    def __init__(self):
        pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        pygame.display.set_caption("Two-Player Pong")
        self.width = 900
        self.height = 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.fps = 60
        self.white = (245, 245, 245)
        self.black = (20, 20, 20)
        self.gray = (120, 120, 120)
        self.font = pygame.font.SysFont("arial", 40)
        self.small_font = pygame.font.SysFont("arial", 28)
        self.paddle_width = 14
        self.paddle_height = 110
        self.paddle_speed = 7
        self.left_paddle = Paddle(
            30,
            self.height // 2 - self.paddle_height // 2,
            self.paddle_width,
            self.paddle_height,
            self.paddle_speed,
            self.white,
        )
        self.right_paddle = Paddle(
            self.width - 30 - self.paddle_width,
            self.height // 2 - self.paddle_height // 2,
            self.paddle_width,
            self.paddle_height,
            self.paddle_speed,
            self.white,
        )
        self.ball = Ball(self.width // 2, self.height // 2, 10, 6, 5, self.white)
        self.left_score = 0
        self.right_score = 0
        self.winning_score = 10
        self.game_over = False
        self.winner_text = ""
        self.round_active = False
        self.serve_timer = 0
        self.serve_delay_frames = 60
    def reset_round(self, direction=1):
        '''
        Reset the ball to the center for a new round and begin a short serve delay.
        The ball launches toward the specified direction after the delay.
        '''
        self.ball.reset(self.width // 2, self.height // 2, direction)
        self.round_active = False
        self.serve_timer = self.serve_delay_frames
    def handle_input(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            self.left_paddle.move_up(0)
        if keys[pygame.K_s]:
            self.left_paddle.move_down(self.height)
        if keys[pygame.K_UP]:
            self.right_paddle.move_up(0)
        if keys[pygame.K_DOWN]:
            self.right_paddle.move_down(self.height)
    def update_serve_state(self):
        if not self.round_active and self.serve_timer > 0:
            self.serve_timer -= 1
            if self.serve_timer <= 0:
                self.round_active = True
    def check_collisions(self):
        if self.ball.y - self.ball.radius <= 0:
            self.ball.y = self.ball.radius
            self.ball.vel_y *= -1
        if self.ball.y + self.ball.radius >= self.height:
            self.ball.y = self.height - self.ball.radius
            self.ball.vel_y *= -1
        ball_rect = self.ball.get_rect()
        if ball_rect.colliderect(self.left_paddle.rect()) and self.ball.vel_x < 0:
            self.ball.x = self.left_paddle.x + self.left_paddle.width + self.ball.radius
            self.ball.vel_x *= -1
            self.ball.increase_speed()
            self.ball.apply_paddle_bounce(self.left_paddle)
        if ball_rect.colliderect(self.right_paddle.rect()) and self.ball.vel_x > 0:
            self.ball.x = self.right_paddle.x - self.ball.radius
            self.ball.vel_x *= -1
            self.ball.increase_speed()
            self.ball.apply_paddle_bounce(self.right_paddle)
    def update_scoring(self):
        '''
        Update scores when the ball passes beyond either side.
        Returns True if a score occurred; otherwise False.
        '''
        if self.ball.x - self.ball.radius > self.width:
            self.left_score += 1
            if self.left_score >= self.winning_score:
                self.game_over = True
                self.winner_text = "Left Player Wins!"
            else:
                self.reset_round(direction=-1)
            return True
        if self.ball.x + self.ball.radius < 0:
            self.right_score += 1
            if self.right_score >= self.winning_score:
                self.game_over = True
                self.winner_text = "Right Player Wins!"
            else:
                self.reset_round(direction=1)
            return True
        return False
    def draw_center_line(self):
        for y in range(0, self.height, 24):
            pygame.draw.rect(self.screen, self.gray, (self.width // 2 - 2, y, 4, 14))
    def draw_score(self):
        left_text = self.font.render(str(self.left_score), True, self.white)
        right_text = self.font.render(str(self.right_score), True, self.white)
        self.screen.blit(left_text, (self.width // 4 - left_text.get_width() // 2, 20))
        self.screen.blit(right_text, (self.width * 3 // 4 - right_text.get_width() // 2, 20))
        threshold_text = self.small_font.render(f"First to {self.winning_score}", True, self.gray)
        self.screen.blit(
            threshold_text,
            (self.width // 2 - threshold_text.get_width() // 2, 70),
        )
    def draw_game_over(self):
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        title = self.font.render(self.winner_text, True, self.white)
        prompt = self.small_font.render("Press R to restart or ESC to quit", True, self.white)
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2, self.height // 2 - 50))
        self.screen.blit(prompt, (self.width // 2 - prompt.get_width() // 2, self.height // 2 + 10))
    def restart(self):
        '''
        Fully restart the match, resetting scores, paddles, ball, and game state.
        '''
        self.left_score = 0
        self.right_score = 0
        self.game_over = False
        self.winner_text = ""
        self.left_paddle.reset(30, self.height // 2 - self.paddle_height // 2)
        self.right_paddle.reset(
            self.width - 30 - self.paddle_width,
            self.height // 2 - self.paddle_height // 2,
        )
        self.reset_round(direction=1)
    def run(self):
        self.reset_round(direction=1)
        while True:
            self.clock.tick(self.fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    if self.game_over and event.key == pygame.K_r:
                        self.restart()
            if not self.game_over:
                self.handle_input()
                self.update_serve_state()
                if self.round_active:
                    self.ball.update()
                    scored = self.update_scoring()
                    if not scored:
                        self.check_collisions()
            self.screen.fill(self.black)
            self.draw_center_line()
            self.left_paddle.draw(self.screen)
            self.right_paddle.draw(self.screen)
            self.ball.draw(self.screen)
            self.draw_score()
            if self.game_over:
                self.draw_game_over()
            pygame.display.flip()