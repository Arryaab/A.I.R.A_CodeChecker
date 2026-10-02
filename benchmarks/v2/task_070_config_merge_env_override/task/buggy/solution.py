from typing import Any, Dict

def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merges override dictionary into base dictionary."""
    result = dict(base)
    # BUG: Shallow update overwrites nested dictionaries completely
    result.update(override)
    return result
