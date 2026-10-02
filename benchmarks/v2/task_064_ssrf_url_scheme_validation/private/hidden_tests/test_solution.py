import pytest
from solution import is_safe_webhook_url

def test_dangerous_schemes_rejected():
    assert is_safe_webhook_url("file:///etc/passwd") is False
    assert is_safe_webhook_url("gopher://127.0.0.1:70") is False

def test_private_subnets_rejected():
    assert is_safe_webhook_url("http://192.168.1.1/admin") is False
    assert is_safe_webhook_url("http://10.0.0.1/") is False
    assert is_safe_webhook_url("http://169.254.169.254/latest/meta-data") is False
