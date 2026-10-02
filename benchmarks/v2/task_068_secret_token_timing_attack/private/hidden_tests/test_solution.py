import hashlib
import hmac
import pytest
from solution import verify_hmac_signature

def test_tampered_payload_rejected():
    secret = "secret_key"
    sig = hmac.new(secret.encode(), b"original", hashlib.sha256).hexdigest()
    assert verify_hmac_signature(b"tampered", sig, secret) is False

def test_wrong_signature_length():
    assert verify_hmac_signature(b"data", "short", "key") is False
