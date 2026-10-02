import pytest
from solution import validate_alphanumeric_token

def test_valid_token():
    assert validate_alphanumeric_token("token123") is True

def test_invalid_characters():
    assert validate_alphanumeric_token("token_123") is False
