INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1

def accumulate_int32(values: list[int]) -> int:
    total = 0
    for v in values:
        total += v
        # BUG: only checks upper bound, fails to check lower bound
        if total > INT32_MAX:
            raise OverflowError("32-bit integer overflow")
    return total
