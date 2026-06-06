'''
Manages the story nodes and player progress through the game.
'''
from story import StoryNode
class StoryManager:
    def __init__(self):
        self.start_node = self.create_story()
        self.current_node = self.start_node
    def create_story(self):
        # Example story setup
        node0 = StoryNode("You found a key on the ground.")
        node1 = StoryNode("You are in a dark forest. You see a path to the left and right.")
        node2 = StoryNode("You took the left path and found a treasure.")
        node3 = StoryNode("You took the right path and encountered a wild animal.")
        node0.add_choice("Pick up the key", node1, lambda player: player.add_item('key'))
        node1.add_choice("Take the left path", node2, lambda player: 'key' in player.inventory)
        node1.add_choice("Take the right path", node3)
        return node0
    def get_current_node(self):
        return self.current_node
    def make_choice(self, choice_index, player):
        if 0 <= choice_index < len(self.current_node.choices):
            choice = self.current_node.choices[choice_index]
            if choice.is_available(player):
                self.current_node = choice.next_node