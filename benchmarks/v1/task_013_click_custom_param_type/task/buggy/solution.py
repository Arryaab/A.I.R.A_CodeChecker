def parse_int_range(val_str: str, min_val: int, max_val: int) -> int:
    val = int(val_str)
    # BUG: uses < and > instead of checking boundaries correctly
    if val <= min_val or val >= max_val:
        raise ValueError(f"Value {val} out of range [{min_val}, {max_val}]")
    return val
