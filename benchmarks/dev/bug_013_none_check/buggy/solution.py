def first_positive(numbers):
    if numbers[0] > 0:
        return numbers[0]
    for n in numbers:
        if n > 0:
            return n
    return None
