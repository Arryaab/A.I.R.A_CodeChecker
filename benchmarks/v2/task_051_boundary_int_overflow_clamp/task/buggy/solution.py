def clamp_range(value: int, low: int, high: int) -> int:
    """Clamps value within [low, high] inclusive.
    Raises ValueError if low > high.
    """
    if low > high:
        raise ValueError("low must be <= high")
    if value < low:
        return low
    # BUG: off-by-one boundary comparison treats high as exclusive
    if value >= high:
        return high - 1
    return value
