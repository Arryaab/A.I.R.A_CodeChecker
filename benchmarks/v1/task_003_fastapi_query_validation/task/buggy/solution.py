import re

def validate_query_param(val: str, min_length: int = 1, max_length: int = 50, pattern: str = None) -> bool:
    if len(val) < min_length:
        return False
    # BUG: uses > instead of <= for max_length validation
    if len(val) >= max_length:
        return False
    if pattern and not re.match(pattern, val):
        return False
    return True
