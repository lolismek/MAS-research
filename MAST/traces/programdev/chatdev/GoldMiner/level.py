'''
Manages the current level's state, including objects and difficulty in the Gold Miner game.
'''
from object import Object
class Level:
    def __init__(self, minimum_gold_value, time_limit, objects):
        self.objects = [Object(x, y, value, weight) for x, y, value, weight in objects]
        self.minimum_gold_value = minimum_gold_value
        self.time_limit = time_limit  # seconds
        self.current_time = 0
    def check_completion(self):
        total_value = sum(obj.value for obj in self.objects if obj.grabbed)
        if total_value >= self.minimum_gold_value or self.current_time >= self.time_limit:
            self.end_level()
            return True
        return False
    def end_level(self):
        # Logic to end the level, such as stopping the game or moving to the next level
        print("Level Complete")
    def draw(self, screen):
        for obj in self.objects:
            obj.draw(screen)