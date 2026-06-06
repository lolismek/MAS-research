'''
Defines the StoryNode and Choice classes for managing story segments and branching choices.
'''
class Choice:
    def __init__(self, text, next_node, condition=None):
        self.text = text
        self.next_node = next_node
        self.condition = condition
    def is_available(self, player):
        if self.condition:
            return self.condition(player)
        return True
class StoryNode:
    def __init__(self, text, choices=None):
        self.text = text
        self.choices = choices if choices else []
    def add_choice(self, choice_text, next_node, condition=None):
        self.choices.append(Choice(choice_text, next_node, condition))