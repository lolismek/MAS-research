"""Pack 26 circles in the unit square, maximizing the sum of radii.

Prints a JSON list of 26 [x, y, r] triples.

Seed strategy (deliberately simple): a uniform 6x5 grid, all circles the same
radius, using 26 of the 30 grid cells. Much better packings exist.
"""

import json

COLS, ROWS = 6, 5
N = 26
R = 1.0 / 12.0  # limited by the 6-column spacing (1/6 between centers)


def pack():
    circles = []
    for j in range(ROWS):
        for i in range(COLS):
            if len(circles) == N:
                break
            x = (2 * i + 1) / (2 * COLS)
            y = (2 * j + 1) / (2 * ROWS)
            circles.append([x, y, R])
    return circles


if __name__ == "__main__":
    print(json.dumps(pack()))
