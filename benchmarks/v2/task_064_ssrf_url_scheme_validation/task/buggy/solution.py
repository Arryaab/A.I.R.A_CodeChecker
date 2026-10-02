from urllib.parse import urlparse

def is_safe_webhook_url(url: str) -> bool:
    """Validates whether a URL is safe for outgoing webhook dispatch."""
    parsed = urlparse(url)
    # BUG: Fails to enforce http/https scheme and only checks trivial string match for 127.0.0.1
    host = parsed.hostname or ""
    if host.lower() in ("localhost", "127.0.0.1"):
        return False
    return True
