def rolling_mean(series: list[float | None], window: int, min_periods: int) -> list[float | None]:
    result = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        sub = series[start:i+1]
        valid = [x for x in sub if x is not None]
        # BUG: checks len(sub) instead of len(valid)
        if len(sub) >= min_periods and valid:
            result.append(sum(valid) / len(valid))
        else:
            result.append(None)
    return result
