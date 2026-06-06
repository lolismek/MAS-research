'''
Manages the player's score.
'''
class ScoreManager:
    def __init__(self):
        self.score = 0
    def add_score(self, points):
        self.score += points