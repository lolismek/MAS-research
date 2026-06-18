'''
daily puzzle data and generation utilities
'''
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import List, Tuple
import random
CategoryGroup = Tuple[str, str, List[str]]  # (category, difficulty, words)
@dataclass(frozen=True)
class Puzzle:
    """Represents a complete daily puzzle."""
    words: List[str]
    groups: List[CategoryGroup]
class PuzzleRepository:
    """
    Provides a deterministic daily puzzle based on the current date.
    The same date always yields the same puzzle. The repository also validates
    that each puzzle contains exactly 16 unique words split into 4 non-
    overlapping groups of 4, and that the intended solution is unambiguous by
    design (i.e., every word appears in exactly one group).
    """
    DIFFICULTY_ORDER = ["yellow", "green", "blue", "purple"]
    def __init__(self) -> None:
        self._puzzles = self._build_puzzles()
        self._validate_puzzles()
    def get_daily_puzzle(self, puzzle_date: date | None = None) -> Puzzle:
        """
        Return the puzzle for the given date (or today).
        The selected puzzle is deterministic for a given date. Only the word
        order is shuffled for presentation; the underlying solution remains
        fixed.
        """
        if puzzle_date is None:
            puzzle_date = date.today()
        seed = int(puzzle_date.strftime("%Y%m%d"))
        rng = random.Random(seed)
        puzzle = self._puzzles[seed % len(self._puzzles)]
        groups = [(category, difficulty, words[:]) for category, difficulty, words in puzzle.groups]
        words = puzzle.words[:]
        rng.shuffle(words)
        return Puzzle(words=words, groups=groups)
    def _validate_puzzles(self) -> None:
        """
        Ensure every stored puzzle is valid and non-overlapping.
        This guards against accidental alternate solutions caused by duplicate
        words or group overlap.
        """
        for puzzle in self._puzzles:
            if len(puzzle.words) != 16:
                raise ValueError("Each puzzle must contain exactly 16 words.")
            if len(set(puzzle.words)) != 16:
                raise ValueError("All 16 puzzle words must be unique.")
            seen: set[str] = set()
            if len(puzzle.groups) != 4:
                raise ValueError("Each puzzle must contain exactly 4 groups.")
            for category, difficulty, words in puzzle.groups:
                if difficulty not in self.DIFFICULTY_ORDER:
                    raise ValueError(f"Invalid difficulty '{difficulty}' in category '{category}'.")
                if len(words) != 4:
                    raise ValueError(f"Group '{category}' must contain exactly 4 words.")
                if len(set(words)) != 4:
                    raise ValueError(f"Group '{category}' contains duplicate words.")
                overlap = seen.intersection(words)
                if overlap:
                    raise ValueError(f"Puzzle groups overlap on words: {sorted(overlap)}")
                seen.update(words)
            if set(puzzle.words) != seen:
                raise ValueError("Puzzle words must exactly match the union of all group words.")
    def _build_puzzles(self) -> List[Puzzle]:
        """Construct a larger library of curated, non-overlapping daily puzzles."""
        puzzles: List[Puzzle] = []
        puzzles.append(
            Puzzle(
                words=[
                    "Mercury", "Venus", "Earth", "Mars",
                    "Oak", "Pine", "Maple", "Birch",
                    "Spoon", "Fork", "Knife", "Plate",
                    "Jazz", "Rock", "Blues", "Pop",
                ],
                groups=[
                    ("Planets in the Solar System", "yellow", ["Mercury", "Venus", "Earth", "Mars"]),
                    ("Trees", "green", ["Oak", "Pine", "Maple", "Birch"]),
                    ("Dining Items", "blue", ["Spoon", "Fork", "Knife", "Plate"]),
                    ("Music Genres", "purple", ["Jazz", "Rock", "Blues", "Pop"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "Python", "Java", "C", "Ruby",
                    "Apple", "Banana", "Cherry", "Date",
                    "Red", "Blue", "Green", "Yellow",
                    "Dog", "Cat", "Horse", "Bird",
                ],
                groups=[
                    ("Programming Languages", "yellow", ["Python", "Java", "C", "Ruby"]),
                    ("Fruits", "green", ["Apple", "Banana", "Cherry", "Date"]),
                    ("Colors", "blue", ["Red", "Blue", "Green", "Yellow"]),
                    ("Animals", "purple", ["Dog", "Cat", "Horse", "Bird"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "Monday", "Tuesday", "Wednesday", "Thursday",
                    "North", "South", "East", "West",
                    "Gold", "Silver", "Bronze", "Copper",
                    "Spring", "Summer", "Autumn", "Winter",
                ],
                groups=[
                    ("Days of the Week", "yellow", ["Monday", "Tuesday", "Wednesday", "Thursday"]),
                    ("Cardinal Directions", "green", ["North", "South", "East", "West"]),
                    ("Metals", "blue", ["Gold", "Silver", "Bronze", "Copper"]),
                    ("Seasons", "purple", ["Spring", "Summer", "Autumn", "Winter"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "Amazon", "Nile", "Mississippi", "Danube",
                    "Circle", "Square", "Triangle", "Rectangle",
                    "Piano", "Guitar", "Drums", "Violin",
                    "Shark", "Eagle", "Lion", "Frog",
                ],
                groups=[
                    ("Rivers", "yellow", ["Amazon", "Nile", "Mississippi", "Danube"]),
                    ("Shapes", "green", ["Circle", "Square", "Triangle", "Rectangle"]),
                    ("Instruments", "blue", ["Piano", "Guitar", "Drums", "Violin"]),
                    ("Animals", "purple", ["Shark", "Eagle", "Lion", "Frog"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "Comet", "Asteroid", "Meteor", "Galaxy",
                    "Rose", "Tulip", "Lily", "Daisy",
                    "Laptop", "Tablet", "Phone", "Monitor",
                    "Bread", "Rice", "Pasta", "Soup",
                ],
                groups=[
                    ("Space Objects", "yellow", ["Comet", "Asteroid", "Meteor", "Galaxy"]),
                    ("Flowers", "green", ["Rose", "Tulip", "Lily", "Daisy"]),
                    ("Devices", "blue", ["Laptop", "Tablet", "Phone", "Monitor"]),
                    ("Foods", "purple", ["Bread", "Rice", "Pasta", "Soup"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "Chair", "Table", "Sofa", "Desk",
                    "Dog", "Wolf", "Fox", "Bear",
                    "Pencil", "Pen", "Marker", "Crayon",
                    "Copper", "Iron", "Tin", "Lead",
                ],
                groups=[
                    ("Furniture", "yellow", ["Chair", "Table", "Sofa", "Desk"]),
                    ("Canines and Bears", "green", ["Dog", "Wolf", "Fox", "Bear"]),
                    ("Writing Tools", "blue", ["Pencil", "Pen", "Marker", "Crayon"]),
                    ("Elements", "purple", ["Copper", "Iron", "Tin", "Lead"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "January", "April", "July", "October",
                    "Sparrow", "Robin", "Eagle", "Falcon",
                    "Circle", "Cube", "Sphere", "Cone",
                    "Piano", "Harp", "Flute", "Drum",
                ],
                groups=[
                    ("Months", "yellow", ["January", "April", "July", "October"]),
                    ("Birds", "green", ["Sparrow", "Robin", "Eagle", "Falcon"]),
                    ("3D Shapes", "blue", ["Circle", "Cube", "Sphere", "Cone"]),
                    ("Musical Instruments", "purple", ["Piano", "Harp", "Flute", "Drum"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "Beach", "Desert", "Forest", "Mountain",
                    "Salmon", "Tuna", "Trout", "Cod",
                    "Clock", "Watch", "Calendar", "Hourglass",
                    "Cotton", "Wool", "Silk", "Linen",
                ],
                groups=[
                    ("Landscapes", "yellow", ["Beach", "Desert", "Forest", "Mountain"]),
                    ("Fish", "green", ["Salmon", "Tuna", "Trout", "Cod"]),
                    ("Timekeepers", "blue", ["Clock", "Watch", "Calendar", "Hourglass"]),
                    ("Fabrics", "purple", ["Cotton", "Wool", "Silk", "Linen"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "Lion", "Tiger", "Leopard", "Jaguar",
                    "Mercury", "Venus", "Earth", "Mars",
                    "Sugar", "Salt", "Pepper", "Cinnamon",
                    "Violin", "Cello", "Harp", "Bass",
                ],
                groups=[
                    ("Big Cats", "yellow", ["Lion", "Tiger", "Leopard", "Jaguar"]),
                    ("Planets", "green", ["Mercury", "Venus", "Earth", "Mars"]),
                    ("Spices", "blue", ["Sugar", "Salt", "Pepper", "Cinnamon"]),
                    ("String Instruments", "purple", ["Violin", "Cello", "Harp", "Bass"]),
                ],
            )
        )
        puzzles.append(
            Puzzle(
                words=[
                    "Blue", "Orange", "Violet", "Indigo",
                    "Shark", "Whale", "Dolphin", "Seal",
                    "Hammer", "Screwdriver", "Wrench", "Pliers",
                    "Spring", "Autumn", "Winter", "Summer",
                ],
                groups=[
                    ("Colors", "yellow", ["Blue", "Orange", "Violet", "Indigo"]),
                    ("Marine Mammals", "green", ["Shark", "Whale", "Dolphin", "Seal"]),
                    ("Tools", "blue", ["Hammer", "Screwdriver", "Wrench", "Pliers"]),
                    ("Seasons", "purple", ["Spring", "Autumn", "Winter", "Summer"]),
                ],
            )
        )
        return puzzles