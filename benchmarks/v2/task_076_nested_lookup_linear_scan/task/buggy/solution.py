from typing import List

def has_required_permissions(assigned_roles: List[str], required_roles: List[str]) -> bool:
    """Verifies whether all required roles are present in assigned roles."""
    # BUG: Linear list scan in inner loop causes O(N * M) quadratic latency on large permission sets
    for req in required_roles:
        if req not in assigned_roles:
            return False
    return True
