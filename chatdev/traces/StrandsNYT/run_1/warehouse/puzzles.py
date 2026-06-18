"""
Puzzle definitions for the Strands-like game.
"""
PUZZLES = {
    "Kitchen Tools": {
        "theme": "Kitchen Tools",
        "board": [
            list("UTENSILS"),
            list("AICNLKDR"),
            list("SPATULAM"),
            list("WHSMOGRE"),
            list("LADLETNO"),
            list("NGSPOUCH"),
        ],
        "theme_words": [
            "spatula",
            "knife",
            "whisk",
            "mop",
            "grater",
            "ladle",
            "tongs",
        ],
        "spangram": "utensils",
        "spangram_path": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (0, 7)],
        "word_paths": {
            "spatula": [(2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6)],
            "knife": [(1, 5), (1, 6), (1, 7), (2, 7), (3, 7)],
            "whisk": [(3, 0), (3, 1), (3, 2), (3, 3), (3, 4)],
            "mop": [(3, 5), (3, 6), (3, 7)],
            "grater": [(4, 7), (4, 6), (4, 5), (4, 4), (4, 3), (4, 2)],
            "ladle": [(4, 0), (4, 1), (4, 2), (4, 3), (4, 4)],
            "tongs": [(5, 0), (5, 1), (5, 2), (5, 3), (5, 4)],
        },
        "hints": [
            "Think of common objects used for cooking and serving.",
            "One theme word is a flat turner used with frying pans.",
            "The spangram describes the whole category.",
        ],
    },
    "Ocean Life": {
        "theme": "Ocean Life",
        "board": [
            list("MARINESE"),
            list("HARKOWHA"),
            list("LEOCTOPU"),
            list("SRAYSEAL"),
            list("FISHCRAB"),
            list("CORALJLY"),
        ],
        "theme_words": [
            "shark",
            "whale",
            "octopus",
            "ray",
            "seal",
            "fish",
            "crab",
            "coral",
            "jelly",
        ],
        "spangram": "marine",
        "spangram_path": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)],
        "word_paths": {
            "shark": [(0, 0), (1, 0), (1, 1), (1, 2), (1, 3)],
            "whale": [(1, 4), (1, 5), (1, 6), (1, 7), (2, 0)],
            "octopus": [(2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (3, 7)],
            "ray": [(3, 1), (3, 2), (3, 3)],
            "seal": [(3, 4), (3, 5), (3, 6), (3, 7)],
            "fish": [(4, 0), (4, 1), (4, 2), (4, 3)],
            "crab": [(4, 4), (4, 5), (4, 6), (4, 7)],
            "coral": [(5, 0), (5, 1), (5, 2), (5, 3), (5, 4)],
            "jelly": [(5, 5), (5, 6), (5, 7), (4, 7), (3, 7)],
        },
        "hints": [
            "The theme includes sea creatures and related living things.",
            "A long word at the center begins with O.",
            "The spangram is another word for sea-related things.",
        ],
    },
}
def get_puzzle_names():
    """Return a list of available puzzle names."""
    return list(PUZZLES.keys())