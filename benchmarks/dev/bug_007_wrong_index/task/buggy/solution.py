def second_largest(numbers):
    if len(numbers) < 2:
        return None
    sorted_nums = sorted(list(set(numbers)))
    return sorted_nums[-1]
