'''
Manages the unlocking of hints based on non-theme words found.
'''
class HintSystem:
    def __init__(self):
        self.non_theme_count = 0
        self.hints = 0
    def increment_non_theme_count(self):
        self.non_theme_count += 1
        if self.non_theme_count % 3 == 0:
            self.hints += 1
    def get_hints(self):
        return self.hints