import math

def pairwise_euclidean(points: list[tuple[float, float]]) -> list[list[float]]:
    n = len(points)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            d = math.sqrt((points[i][0] - points[j][0])**2 + (points[i][1] - points[j][1])**2)
            dist[i][j] = d
            # BUG: forgets to mirror dist[j][i]
    return dist
