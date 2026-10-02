import json

def canonical_json(data) -> str:
    """Produces canonical JSON with sorted keys and no unnecessary whitespace."""
    # BUG: Only sorts top-level keys if data is a dict, not handling nested structures
    return json.dumps(data, sort_keys=True, separators=(",", ":"))
