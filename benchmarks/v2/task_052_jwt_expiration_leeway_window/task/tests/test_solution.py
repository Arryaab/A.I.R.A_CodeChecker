import pytest
from solution import is_token_expired

def test_token_clearly_valid():
    assert is_token_expired(exp_timestamp=1000, current_timestamp=500) is False

def test_token_clearly_expired():
    assert is_token_expired(exp_timestamp=1000, current_timestamp=2000) is True

def test_negative_leeway_error():
    with pytest.raises(ValueError):
        is_token_expired(1000, 1000, leeway_seconds=-10)
