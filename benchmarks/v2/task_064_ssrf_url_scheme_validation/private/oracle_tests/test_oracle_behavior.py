import pytest
from solution import is_safe_webhook_url

def test_oracle_ssrf_corpus():
    bad = [
        "http://127.0.0.1/", "http://[::1]/", "file:///bin/sh",
        "http://10.255.255.1/", "ftp://example.com"
    ]
    for u in bad:
        assert is_safe_webhook_url(u) is False
