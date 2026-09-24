def max_of_three(a, b, c):
    max_val = a
    if b > max_val:
        max_val = b
    if c < max_val:
        max_val = c
    return max_val
