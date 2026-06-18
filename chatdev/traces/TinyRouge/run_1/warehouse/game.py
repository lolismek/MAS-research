'''
Game loop, input handling, rendering, combat resolution, and level progression.
'''
import pygame
from mapgen import MapGenerator
from entities import Player
class Game:
    TILE_SIZE = 10
    MAP_W = 80
    MAP_H = 80
    HUD_W = 220
    SCREEN_W = MAP_W * TILE_SIZE + HUD_W
    SCREEN_H = MAP_H * TILE_SIZE
    FPS = 60
    MAX_HP = 9999
    COLOR_BG = (18, 18, 24)
    COLOR_FLOOR = (210, 210, 210)
    COLOR_WALL = (55, 55, 75)
    COLOR_PLAYER = (60, 170, 255)
    COLOR_MONSTER = (220, 80, 80)
    COLOR_CHEST = (240, 200, 70)
    COLOR_DOOR = (120, 220, 120)
    COLOR_TEXT = (240, 240, 240)
    COLOR_PANEL = (28, 28, 36)
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Tower of the Sorcerer - Roguelike")
        self.screen = pygame.display.set_mode((self.SCREEN_W, self.SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.level = 1
        self.generator = MapGenerator(self.MAP_W, self.MAP_H)
        self.tilemap = self.generator.generate_level(self.level)
        self.player = Player(self.tilemap.start_x, self.tilemap.start_y, hp=100)
        self.game_over = False
        self.message = "Use W/A/S/D to move."
        self.last_monster = None
    def reset_level(self, message=None):
        self.tilemap = self.generator.generate_level(self.level)
        self.player.x = self.tilemap.start_x
        self.player.y = self.tilemap.start_y
        self.last_monster = None
        self.message = message if message is not None else f"Entered level {self.level}."
    def resolve_combat(self, monster):
        """
        Resolve combat by subtracting the monster's HP from the player's HP.
        This is done once per encounter, then the monster is removed from the map.
        """
        self.last_monster = monster
        self.player.hp -= monster.hp
        self.tilemap.remove_monster(monster.x, monster.y)
        self.message = f"Encountered monster: -{monster.hp} HP."
        if self.player.hp <= 0:
            self.player.hp = 0
            self.game_over = True
            self.message = "Game Over. Press R to restart."
    def move_player(self, dx, dy):
        if self.game_over:
            return
        nx = self.player.x + dx
        ny = self.player.y + dy
        if not self.tilemap.in_bounds(nx, ny):
            return
        if self.tilemap.is_wall(nx, ny):
            self.message = "A wall blocks your way."
            return
        # Move only on floor tiles.
        self.player.x = nx
        self.player.y = ny
        # Door check: advance level with a clear message.
        if self.tilemap.is_door(nx, ny):
            self.level += 1
            self.reset_level(message="You reached the door. Next level!")
            return
        # Chest interaction: immediate HP restore.
        if self.tilemap.has_chest(nx, ny):
            heal = self.tilemap.pickup_chest(nx, ny)
            self.player.hp = min(self.MAX_HP, self.player.hp + heal)
            self.message = f"Found a chest. Recovered {heal} HP."
            return
        # Monster interaction: subtract monster HP from player HP exactly once.
        if self.tilemap.has_monster(nx, ny):
            monster = self.tilemap.get_monster(nx, ny)
            if monster is not None:
                self.resolve_combat(monster)
            return
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and not self.game_over:
                if event.key == pygame.K_w:
                    self.move_player(0, -1)
                elif event.key == pygame.K_s:
                    self.move_player(0, 1)
                elif event.key == pygame.K_a:
                    self.move_player(-1, 0)
                elif event.key == pygame.K_d:
                    self.move_player(1, 0)
            if event.type == pygame.KEYDOWN and self.game_over:
                if event.key == pygame.K_r:
                    self.level = 1
                    self.player.hp = 100
                    self.game_over = False
                    self.reset_level(message="Use W/A/S/D to move.")
        return True
    def draw_tile(self, x, y, color):
        pygame.draw.rect(
            self.screen,
            color,
            pygame.Rect(
                x * self.TILE_SIZE,
                y * self.TILE_SIZE,
                self.TILE_SIZE,
                self.TILE_SIZE,
            ),
        )
    def draw_map(self):
        for y in range(self.MAP_H):
            for x in range(self.MAP_W):
                if self.tilemap.is_wall(x, y):
                    self.draw_tile(x, y, self.COLOR_WALL)
                else:
                    self.draw_tile(x, y, self.COLOR_FLOOR)
        for chest in self.tilemap.chests:
            self.draw_tile(chest.x, chest.y, self.COLOR_CHEST)
        for monster in self.tilemap.monsters.values():
            self.draw_tile(monster.x, monster.y, self.COLOR_MONSTER)
        self.draw_tile(self.tilemap.door_x, self.tilemap.door_y, self.COLOR_DOOR)
        self.draw_tile(self.player.x, self.player.y, self.COLOR_PLAYER)
    def draw_hud(self):
        panel_x = self.MAP_W * self.TILE_SIZE
        pygame.draw.rect(
            self.screen,
            self.COLOR_PANEL,
            pygame.Rect(panel_x, 0, self.HUD_W, self.SCREEN_H),
        )
        lines = [
            f"Level: {self.level}",
            f"HP: {self.player.hp}",
            "",
            "Controls:",
            "W/A/S/D = Move",
            "",
            "Status:",
            self.message,
        ]
        if self.last_monster is not None:
            lines += [
                "",
                "Last Monster:",
                f"HP: {self.last_monster.hp}",
                f"Pos: ({self.last_monster.x}, {self.last_monster.y})",
            ]
        if self.game_over:
            lines += ["", "GAME OVER", "Press R to restart"]
        y = 20
        for line in lines:
            surface = self.font.render(line, True, self.COLOR_TEXT)
            self.screen.blit(surface, (panel_x + 12, y))
            y += 26 if line == "" else 20
    def draw(self):
        self.screen.fill(self.COLOR_BG)
        self.draw_map()
        self.draw_hud()
        pygame.display.flip()
    def run(self):
        running = True
        while running:
            running = self.handle_input()
            self.draw()
            self.clock.tick(self.FPS)
        pygame.quit()