def matrix_power(matrix: list[list[float]], power: int) -> list[list[float]]:
    n = len(matrix)
    if power == 0:
        # BUG: returns zero matrix instead of identity matrix
        return [[0.0 for _ in range(n)] for _ in range(n)]
    res = [row[:] for row in matrix]
    for _ in range(power - 1):
        new_res = [[0.0 for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    new_res[i][j] += res[i][k] * matrix[k][j]
        res = new_res
    return res
