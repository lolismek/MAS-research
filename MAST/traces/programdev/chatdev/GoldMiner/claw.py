'''
Represents the claw that moves and grabs objects in the Gold Miner game.
'''
import pygame
class Claw:
    def __init__(self):
        self.position = [400, 50]
        self.direction = 1
        self.grabbed_object = None
        self.reeling = False
    def move(self):
        if self.grabbed_object is None and not self.reeling:
            self.position[0] += self.direction * 5
            if self.position[0] <= 0 or self.position[0] >= 800:
                self.direction *= -1
        elif self.reeling:
            self.reel_in()
    def grab(self, objects):
        if self.grabbed_object is None:
            for obj in objects:
                if obj.is_within_reach(self.position):
                    self.grabbed_object = obj
                    self.reeling = True
                    break
    def reel_in(self):
        if self.grabbed_object:
            self.position[1] -= 5
            if self.position[1] <= 50:
                self.position[1] = 50
                self.reeling = False
                self.grabbed_object.grabbed = True  # Mark the object as grabbed
                self.grabbed_object = None
    def draw(self, screen):
        pygame.draw.line(screen, (255, 255, 255), (self.position[0], 0), self.position, 2)
        if self.grabbed_object:
            self.grabbed_object.position = self.position
            self.grabbed_object.draw(screen)