from collections import deque
from typing import Dict, List

class CycleDetectedError(Exception):
    pass

def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
    """Returns valid topological order or raises CycleDetectedError."""
    in_degree = {u: 0 for u in graph}
    for u in graph:
        for v in graph[u]:
            if v in in_degree:
                in_degree[v] += 1
            else:
                in_degree[v] = 1

    queue = deque([u for u, deg in in_degree.items() if deg == 0])
    order = []

    while queue:
        u = queue.popleft()
        order.append(u)
        for v in graph.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    # BUG: Fails to check whether all nodes were visited, returning incomplete list on cycle
    return order
