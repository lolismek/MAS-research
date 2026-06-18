'''
Procedural 80x80 map generation with a guaranteed path from start to door.
A connectivity check verifies the path and regenerates if needed.
Monsters and chests are placed only on reachable tiles off the guaranteed path.
'''
import random
from collections import deque
from entities import Chest, Monster
from tilemap import TileMap
class MapGenerator:
    def __init__(self, width, height):
        self.width = width
        self.height = height
    def generate_level(self, level_num):
        rng = random.Random(level_num * 1000 + 42)
        for _ in range(20):
            tilemap = TileMap(self.width, self.height)
            # Fixed start and door positions.
            tilemap.start_x, tilemap.start_y = 2, 2
            tilemap.door_x, tilemap.door_y = self.width - 3, self.height - 3
            # Fill the map with walls first.
            tilemap.fill_walls()
            # Carve a guaranteed path from start to door.
            path = self._carve_path(
                tilemap.start_x,
                tilemap.start_y,
                tilemap.door_x,
                tilemap.door_y,
                rng,
            )
            for x, y in path:
                tilemap.set_floor(x, y)
            # Add some extra rooms/space without affecting guaranteed path connectivity.
            self._open_random_rooms(tilemap, rng, count=10 + level_num)
            # Ensure start and door are floor tiles.
            tilemap.set_floor(tilemap.start_x, tilemap.start_y)
            tilemap.set_floor(tilemap.door_x, tilemap.door_y)
            # Verify connectivity explicitly.
            if not self._is_reachable(tilemap, (tilemap.start_x, tilemap.start_y), (tilemap.door_x, tilemap.door_y)):
                continue
            # Place chests and monsters only on reachable cells, excluding the path.
            reachable = self._reachable_cells(tilemap, (tilemap.start_x, tilemap.start_y))
            self._place_entities(tilemap, rng, level_num, excluded_cells=set(path), reachable_cells=reachable)
            return tilemap
        # Fallback: deterministic straight corridor if regeneration fails.
        tilemap = TileMap(self.width, self.height)
        tilemap.start_x, tilemap.start_y = 2, 2
        tilemap.door_x, tilemap.door_y = self.width - 3, self.height - 3
        tilemap.fill_walls()
        x, y = tilemap.start_x, tilemap.start_y
        while x != tilemap.door_x:
            tilemap.set_floor(x, y)
            x += 1 if x < tilemap.door_x else -1
        while y != tilemap.door_y:
            tilemap.set_floor(x, y)
            y += 1 if y < tilemap.door_y else -1
        tilemap.set_floor(tilemap.door_x, tilemap.door_y)
        reachable = self._reachable_cells(tilemap, (tilemap.start_x, tilemap.start_y))
        self._place_entities(tilemap, rng, level_num, excluded_cells=set(), reachable_cells=reachable)
        return tilemap
    def _carve_path(self, sx, sy, dx, dy, rng):
        x, y = sx, sy
        path = [(x, y)]
        # Randomized Manhattan walk that always reaches the door.
        while (x, y) != (dx, dy):
            moves = []
            if x < dx:
                moves.append((1, 0))
            if x > dx:
                moves.append((-1, 0))
            if y < dy:
                moves.append((0, 1))
            if y > dy:
                moves.append((0, -1))
            if rng.random() < 0.35 and len(moves) > 1:
                moves.extend(moves)
            mx, my = rng.choice(moves)
            x += mx
            y += my
            path.append((x, y))
        return path
    def _open_random_rooms(self, tilemap, rng, count=10):
        for _ in range(count):
            cx = rng.randint(5, self.width - 6)
            cy = rng.randint(5, self.height - 6)
            rw = rng.randint(2, 5)
            rh = rng.randint(2, 5)
            for y in range(cy - rh, cy + rh + 1):
                for x in range(cx - rw, cx + rw + 1):
                    if tilemap.in_bounds(x, y):
                        tilemap.set_floor(x, y)
    def _reachable_cells(self, tilemap, start):
        sx, sy = start
        if not tilemap.is_floor(sx, sy):
            return set()
        q = deque([(sx, sy)])
        visited = {(sx, sy)}
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not tilemap.in_bounds(nx, ny):
                    continue
                if (nx, ny) in visited:
                    continue
                if not tilemap.is_floor(nx, ny):
                    continue
                visited.add((nx, ny))
                q.append((nx, ny))
        return visited
    def _is_reachable(self, tilemap, start, goal):
        return goal in self._reachable_cells(tilemap, start)
    def _place_entities(self, tilemap, rng, level_num, excluded_cells=None, reachable_cells=None):
        if excluded_cells is None:
            excluded_cells = set()
        if reachable_cells is None:
            reachable_cells = set()
        candidate_cells = []
        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                if not tilemap.is_floor(x, y):
                    continue
                if reachable_cells and (x, y) not in reachable_cells:
                    continue
                if (x, y) in excluded_cells:
                    continue
                if (x, y) == (tilemap.start_x, tilemap.start_y):
                    continue
                if (x, y) == (tilemap.door_x, tilemap.door_y):
                    continue
                candidate_cells.append((x, y))
        rng.shuffle(candidate_cells)
        chest_count = 10 + level_num * 2
        monster_count = 12 + level_num * 3
        # Place chests first, then monsters, using unique cells only.
        for _ in range(chest_count):
            if not candidate_cells:
                break
            x, y = candidate_cells.pop()
            heal = rng.randint(20, 30)
            tilemap.chests.append(Chest(x, y, heal))
        for _ in range(monster_count):
            if not candidate_cells:
                break
            x, y = candidate_cells.pop()
            hp = rng.randint(5 + level_num * 2, 15 + level_num * 4)
            tilemap.monsters[(x, y)] = Monster(x, y, hp)