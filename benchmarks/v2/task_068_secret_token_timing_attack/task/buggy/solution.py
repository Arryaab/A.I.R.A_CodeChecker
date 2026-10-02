import hashlib
import hmac

def verify_hmac_signature(payload: bytes, signature_hex: str, secret: str) -> bool:
    """Verifies HMAC SHA-256 signature."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    # BUG: Early-exit string equality leaks timing information
    return signature_hex == expected
