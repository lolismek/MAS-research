from collections import defaultdict

def build_graph(cells):
    graph = defaultdict(list)
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    
    for r, c in cells:
        for dr, dc in directions:
            if (r + dr, c + dc) in cells:
                graph[(r, c)].append((r + dr, c + dc))
                
    return graph

def check_eulerian_circuit(cells):
    graph = build_graph(cells)
    
    # Check all vertices have even degree
    for node in graph:
        if len(graph[node]) % 2 != 0:
            return False
    
    # Check if the graph is connected
    # Use DFS to see if we can reach all nodes from an arbitrary start node
    def dfs(node, visited):
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                dfs(neighbor, visited)
    
    visited = set()
    start_node = cells[0]
    dfs(start_node, visited)
    
    return len(visited) == len(graph)

filename = '5cfb274c-0207-4aa7-9575-6ac0bd95d9b2.xlsx'
green_cells = [(1, 3), (1, 4), (2, 2), (2, 3), (3, 2), (3, 5), (3, 6), (4, 2), (4, 6), (5, 2), (5, 6),
               (6, 2), (6, 6), (6, 7), (7, 2), (7, 6), (7, 7), (8, 2), (8, 3), (8, 6), (8, 7),
               (9, 3), (9, 6), (9, 7), (10, 3), (10, 6), (10, 7), (11, 3), (11, 5), (11, 6), (11, 7),
               (12, 3), (12, 5), (12, 6), (13, 2), (13, 3), (13, 5), (13, 6), (14, 2), (14, 5),
               (14, 6), (15, 2), (15, 5), (15, 6), (16, 2), (16, 3), (16, 4), (16, 5), (16, 6)]

can_form_eulerian_circuit = check_eulerian_circuit(green_cells)
print("Can Earl traverse all his plots and return to the start without backtracking?", can_form_eulerian_circuit)
