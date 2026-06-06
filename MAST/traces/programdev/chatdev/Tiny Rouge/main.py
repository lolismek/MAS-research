'''
Main entry point for the roguelike game. Initializes and runs the game loop.
'''
import pygame
from player import Player
from map import Map
from ui import UI
from monster import Monster
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((800, 800))
        pygame.display.set_caption("Roguelike Game")
        self.clock = pygame.time.Clock()
        self.map = Map()
        self.player = Player(self.map.start_position)
        self.ui = UI(self.screen, self.player)
        self.monsters = self.map.place_monsters()
        self.treasure_chests = self.map.place_treasure_chests()
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_w:
                        self.player.move('up', self.map)
                    elif event.key == pygame.K_s:
                        self.player.move('down', self.map)
                    elif event.key == pygame.K_a:
                        self.player.move('left', self.map)
                    elif event.key == pygame.K_d:
                        self.player.move('right', self.map)
            self.check_interactions()
            self.screen.fill((0, 0, 0))
            self.ui.draw(self.map, self.monsters, self.treasure_chests)
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()
    def check_interactions(self):
        for monster in self.monsters:
            if (self.player.x, self.player.y) == (monster.x, monster.y):
                self.player.combat(monster)
                if monster.hp <= 0:
                    self.monsters.remove(monster)
        for chest in self.treasure_chests:
            if (self.player.x, self.player.y) == chest:
                self.player.collect_treasure()
                self.treasure_chests.remove(chest)
if __name__ == "__main__":
    game = Game()
    game.run()