'''
Generates a new puzzle each day.
'''
from puzzle import Puzzle
import datetime
class DailyPuzzle:
    def __init__(self):
        self.puzzles = self.load_puzzles()
    def load_puzzles(self):
        # Load or define multiple puzzles here
        return [
            Puzzle(
                ["apple", "banana", "cherry", "date", "dog", "cat", "fish", "bird", "red", "blue", "green", "yellow", "car", "bus", "bike", "train"],
                {"fruits": ["apple", "banana", "cherry", "date"], "animals": ["dog", "cat", "fish", "bird"], "colors": ["red", "blue", "green", "yellow"], "vehicles": ["car", "bus", "bike", "train"]},
                {"fruits": "yellow", "animals": "green", "colors": "blue", "vehicles": "purple"}
            ),
            Puzzle(
                ["pear", "peach", "plum", "grape", "lion", "tiger", "bear", "wolf", "pink", "orange", "purple", "black", "plane", "boat", "submarine", "helicopter"],
                {"fruits": ["pear", "peach", "plum", "grape"], "animals": ["lion", "tiger", "bear", "wolf"], "colors": ["pink", "orange", "purple", "black"], "vehicles": ["plane", "boat", "submarine", "helicopter"]},
                {"fruits": "yellow", "animals": "green", "colors": "blue", "vehicles": "purple"}
            ),
            # Add more puzzles as needed
        ]
    def generate_puzzle(self):
        # Generate a puzzle based on the current date
        today = datetime.date.today()
        # Use a hash of the date to ensure a unique puzzle each day
        index = hash(today) % len(self.puzzles)
        return self.puzzles[index]