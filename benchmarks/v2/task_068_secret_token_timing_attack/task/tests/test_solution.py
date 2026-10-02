import hashlib
import hmac
import pytest
from solution import verify_hmac_signature

def test_valid_hmac():
    secret = "secret_key"
    payload = b"hello world"
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_hmac_signature(payload, sig, secret) is True
