books = [
    {"title": "Fire and Blood", "words": 176500, "days": 44},
    {"title": "Song of Solomon", "words": 84250, "days": 48},
    {"title": "The Lost Symbol", "words": 127250, "days": 66},
    {"title": "2001: A Space Odyssey", "words": 80000, "days": 23},
    {"title": "American Gods", "words": 165250, "days": 50},
    {"title": "Out of the Silent Planet", "words": 64000, "days": 36},
    {"title": "The Andromeda Strain", "words": 76000, "days": 30},
    {"title": "Brave New World", "words": 63766, "days": 19},
    {"title": "Silence", "words": 100000, "days": 33},  # Approximate value
    {"title": "The Shining", "words": 160863, "days": 6},
]

slowest_book = None
slowest_rate = float('inf')

for book in books:
    words_per_day = book['words'] / book['days']
    print(f"{book['title']} - {words_per_day:.2f} words/day")
    if words_per_day < slowest_rate:
        slowest_rate = words_per_day
        slowest_book = book['title']

print(f"The book read the slowest is '{slowest_book}' with {slowest_rate:.2f} words per day.")
