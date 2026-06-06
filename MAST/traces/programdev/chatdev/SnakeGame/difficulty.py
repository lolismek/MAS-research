'''
Difficulty class to manage game difficulty levels.
'''
class Difficulty:
    def __init__(self, level='medium'):
        self.level = level
        self.speeds = {'easy': 10, 'medium': 20, 'hard': 30}
    def get_speed(self):
        return self.speeds.get(self.level, 20)