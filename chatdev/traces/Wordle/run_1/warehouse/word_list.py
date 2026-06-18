'''
Word lists for the terminal Wordle game.
ANSWER_LIST contains the words eligible to be the daily solution.
VALID_GUESS_LIST contains accepted 5-letter words for validation and scoring.
All entries are validated to be exactly 5-letter alphabetic strings.
'''
ANSWER_LIST = [
    "about", "above", "actor", "adapt", "admit", "adult", "after", "again", "agent", "agree",
    "alarm", "alive", "allow", "alone", "among", "angle", "apple", "arena", "argue", "arise",
    "audio", "aware", "basic", "beach", "began", "begin", "being", "below", "blame", "blind",
    "block", "board", "brain", "brand", "brave", "bread", "break", "brown", "build", "cabin",
    "carry", "catch", "cause", "chain", "chair", "chant", "chart", "check", "cheer", "chess",
    "chief", "child", "clean", "clear", "click", "clock", "close", "cloud", "coach", "coast",
    "cover", "crane", "cream", "crime", "cross", "crown", "daily", "dance", "doubt", "dozen",
    "draft", "dream", "drive", "earth", "equal", "event", "every", "extra", "faith", "false",
    "field", "fight", "final", "flame", "floor", "force", "frame", "fresh", "front", "fruit",
    "giant", "glass", "glove", "grace", "grade", "grain", "grand", "grant", "grape", "green",
    "group", "guard", "guest", "happy", "heart", "heavy", "honor", "house", "human", "image",
    "index", "inner", "joint", "judge", "jolly", "knife", "later", "level", "light", "limit",
    "logic", "lucky", "magic", "major", "maker", "march", "money", "music", "naive", "noble",
    "noise", "north", "novel", "ocean", "offer", "other", "paint", "party", "peace", "phase",
    "phone", "piece", "pilot", "plain", "plant", "plate", "power", "press", "price", "pride",
    "queen", "quick", "quiet", "radio", "raise", "range", "ready", "right", "river", "roast",
    "round", "rough", "route", "scale", "scene", "scope", "score", "sense", "shape", "share",
    "sheep", "shine", "shirt", "shock", "skill", "sleep", "smile", "sound", "space", "spare",
    "speak", "speed", "spice", "spoke", "sport", "stare", "start", "steam", "still", "stone",
    "storm", "story", "style", "sugar", "swift", "table", "taste", "teach", "thank", "theme",
    "there", "thing", "think", "thick", "third", "those", "throw", "tight", "today", "topic",
    "trace", "train", "trend", "trust", "truth", "uncle", "under", "union", "urban", "value",
    "vapor", "video", "visit", "voice", "watch", "water", "wheel", "where", "white", "whole",
    "woman", "world", "young"
]
VALID_GUESS_LIST = sorted(set(ANSWER_LIST) | {
    "abide", "acute", "adore", "adopt", "affix", "aging", "aisle", "alert", "amuse",
    "anime", "ankle", "apron", "aside", "asset", "attic", "award", "baker", "banjo",
    "beard", "boost", "bored", "broom", "cider", "civic", "couch", "curry", "debug", "defer",
    "deity", "evoke", "fable", "fancy", "fatal", "glide", "grind", "hinge", "ideal", "jeans",
    "lemon", "mango", "ninja", "orbit", "pearl", "piano", "proof", "rebel", "saint", "spoon",
    "squad", "stool", "tease", "unite", "vivid", "woven", "yield", "zebra"
})
# Startup integrity checks for standalone import/use.
for _word in ANSWER_LIST:
    if not (isinstance(_word, str) and len(_word) == 5 and _word.isalpha()):
        raise ValueError(f"Invalid answer word detected: {_word!r}")
for _word in VALID_GUESS_LIST:
    if not (isinstance(_word, str) and len(_word) == 5 and _word.isalpha()):
        raise ValueError(f"Invalid valid-guess word detected: {_word!r}")