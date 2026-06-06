import geopy.distance

# ASEAN capitals with their geographical coordinates (latitude, longitude)
capitals = {
    "Bandar Seri Begawan": (4.9031, 114.9398),
    "Phnom Penh": (11.5564, 104.9282),
    "Jakarta": (-6.2088, 106.8456),
    "Vientiane": (17.9757, 102.6331),
    "Kuala Lumpur": (3.1390, 101.6869),
    "Naypyidaw": (19.7633, 96.0785),
    "Manila": (14.5995, 120.9842),
    "Singapore": (1.3521, 103.8198),
    "Bangkok": (13.7563, 100.5018),
    "Hanoi": (21.0285, 105.8542)
}

# Initialize variables to track the maximum distance and corresponding capitals
max_distance = 0
furthest_capitals = ()

# Calculate distances between all pairs of capitals
for city1, coord1 in capitals.items():
    for city2, coord2 in capitals.items():
        if city1 != city2:
            distance = geopy.distance.distance(coord1, coord2).kilometers
            if distance > max_distance:
                max_distance = distance
                furthest_capitals = (city1, city2)

# Ordering the capital names alphabetically
furthest_capitals = tuple(sorted(furthest_capitals))

# Output the furthest capital cities and their distance
print(f"Furthest Capitals: {furthest_capitals[0]}, {furthest_capitals[1]} with a distance of {max_distance:.2f} km")
