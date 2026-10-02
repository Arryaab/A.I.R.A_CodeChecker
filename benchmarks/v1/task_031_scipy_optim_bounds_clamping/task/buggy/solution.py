def project_box_bounds(x: list[float], bounds: list[tuple[float, float]]) -> list[float]:
    projected = []
    for val, (l, u) in zip(x, bounds):
        # BUG: inverts min and max clamping
        projected.append(min(l, max(u, val)))
    return projected
