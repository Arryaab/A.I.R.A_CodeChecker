import base64
import json

def decode_cursor(cursor_token: str) -> int:
    """Decodes cursor token into integer record offset."""
    # BUG: Assumes cursor is always base64 JSON, failing on legacy integer string offsets like '50'
    raw = base64.b64decode(cursor_token.encode()).decode()
    data = json.loads(raw)
    return int(data["offset"])
