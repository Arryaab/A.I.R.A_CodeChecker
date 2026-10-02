import pytest
from solution import is_domain_match

def test_oracle_happy_path_exact():
    assert is_domain_match("example.com", "example.com") is True
    assert is_domain_match("EXAMPLE.COM", "example.com") is True

def test_oracle_happy_path_subdomain():
    assert is_domain_match("api.example.com", "example.com") is True
    assert is_domain_match("sub.domain.example.com", "example.com") is True
    assert is_domain_match("api.example.com", ".example.com") is True

def test_oracle_negative_suffix_spoofing():
    # Security: attackerexample.com MUST NOT match example.com
    assert is_domain_match("notexample.com", "example.com") is False
    assert is_domain_match("attackerexample.com", "example.com") is False
    assert is_domain_match("fakeexample.com", ".example.com") is False
