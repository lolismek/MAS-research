# Define the operation table
operation_table = {
    'a': {'a': 'a', 'b': 'b', 'c': 'c', 'd': 'b', 'e': 'd'},
    'b': {'a': 'b', 'b': 'c', 'c': 'a', 'd': 'e', 'e': 'c'},
    'c': {'a': 'c', 'b': 'a', 'c': 'b', 'd': 'b', 'e': 'a'},
    'd': {'a': 'b', 'b': 'e', 'c': 'b', 'd': 'e', 'e': 'd'},
    'e': {'a': 'd', 'b': 'b', 'c': 'a', 'd': 'd', 'e': 'c'},
}

# Initialize a set to hold elements involved in non-commutative examples
non_commutative_elements = set()

# Check every pair (x, y) to see if x * y == y * x
for x in operation_table:
    for y in operation_table[x]:
        if operation_table[x][y] != operation_table[y][x]:
            non_commutative_elements.update([x, y])

# Sort the list and join by commas
result = ', '.join(sorted(non_commutative_elements))

# Output the result
print(result)
