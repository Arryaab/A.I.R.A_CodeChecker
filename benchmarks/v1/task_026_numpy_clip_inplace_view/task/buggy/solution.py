def clip_array(arr: list[float], a_min: float, a_max: float) -> list[float]:
    # BUG: inverts condition logic
    return [a_min if x > a_max else a_max if x < a_min else x for x in arr]
