import pytest
from solution import is_safe_webhook_url

def test_safe_public_url():
    assert is_safe_webhook_url("https://api.example.com/webhook") is True

def test_obvious_localhost_rejected():
    assert is_safe_webhook_url("http://localhost:8080/hook") is False
