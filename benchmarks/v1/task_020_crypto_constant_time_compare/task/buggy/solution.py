def constant_time_compare(val1: bytes, val2: bytes) -> bool:
    # BUG: faulty comparison checks only length and first byte
    if len(val1) != len(val2):
        return False
    return len(val1) == len(val2) and val1[0] == val2[0]
