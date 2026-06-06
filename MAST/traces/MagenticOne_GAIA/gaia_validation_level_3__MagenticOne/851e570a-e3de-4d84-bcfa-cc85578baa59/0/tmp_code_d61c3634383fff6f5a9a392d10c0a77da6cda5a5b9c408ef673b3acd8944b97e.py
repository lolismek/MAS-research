import itertools

# Boggle board configuration
boggle_board = [
    ['A', 'B', 'R', 'L'],
    ['E', 'I', 'T', 'E'],
    ['I', 'O', 'N', 'S'],
    ['F', 'P', 'E', 'I']
]

# Directions for moving in 8 possible directions on the board (up, down, left, right, and diagonals)
directions = [(-1, -1), (-1, 0), (-1, 1),
              (0, -1), (0, 1),
              (1, -1), (1, 0), (1, 1)]

# Read dictionary
def load_dictionary():
    with open('words_alpha.txt', 'r', encoding='utf-8') as file:
        return set(word.strip().lower() for word in file)

# Check if position is valid on the board
def is_valid_position(x, y, visited):
    return (0 <= x < 4) and (0 <= y < 4) and not visited[x][y]

# Perform DFS to find words from the board
def search_word(x, y, board, visited, word, valid_words):
    # Mark the current position as visited
    visited[x][y] = True
    word += board[x][y]
    
    # If the word is valid, add to the valid_words list
    if word in dictionary:
        valid_words.add(word)

    # Explore all 8 directions
    for dx, dy in directions:
        new_x, new_y = x + dx, y + dy
        if is_valid_position(new_x, new_y, visited):
            search_word(new_x, new_y, board, visited, word, valid_words)
    
    # Unmark the current position
    visited[x][y] = False

# Main function to find the longest word
def find_longest_word(board):
    global dictionary
    dictionary = load_dictionary()
    longest_word = ""
    valid_words = set()
    
    for i in range(4):
        for j in range(4):
            visited = [[False] * 4 for _ in range(4)]
            search_word(i, j, board, visited, "", valid_words)
    
    # Find the longest word based on length and then alphabetically
    longest_word = max(sorted(valid_words), key=lambda x: (len(x), x), default="")
    return longest_word

# Find and print the longest word in the Boggle board
longest_word = find_longest_word(boggle_board)
print(f"The longest word is: {longest_word}")
