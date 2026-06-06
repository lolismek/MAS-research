house_positions = [0, 7, 10, 14, 21, 24, 31]
house_positions.sort()  # Ensure the list is sorted

towers = 0
n = len(house_positions)
i = 0

while i < n:
    towers += 1
    # Place the tower at the farthest house within 4 miles of the current house
    location = house_positions[i] + 4
    # Move the index to the rightmost house that this tower can cover
    while i < n and house_positions[i] <= location:
        i += 1
    # Now, location marks the farthest house covered by the current tower

print(towers)
