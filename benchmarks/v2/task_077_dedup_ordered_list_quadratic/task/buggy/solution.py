from typing import List

def deduplicate_preserve_order(items: List[int]) -> List[int]:
    """Deduplicates list while preserving first appearance order."""
    # BUG: Quadratic lookup 'if x not in seen' on list causes O(N^2) slowdown
    seen = []
    for x in items:
        if x not in seen:
            seen.append(x)
    return seen
