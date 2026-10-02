import math

def nanmean_masked(data: list[float], mask: list[bool]) -> float:
    valid_elements = []
    for x, m in zip(data, mask):
        if not m:
            # BUG: forgets to check math.isnan(x)
            valid_elements.append(x)
    if not valid_elements:
        return float('nan')
    return sum(valid_elements) / len(valid_elements)
