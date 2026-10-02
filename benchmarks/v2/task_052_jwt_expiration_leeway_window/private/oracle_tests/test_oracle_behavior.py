import pytest
from solution import is_token_expired

def test_oracle_leeway_properties():
    now = 1700000000
    for leeway in [0, 15, 60, 300]:
        assert is_token_expired(now, now, leeway) is False
        assert is_token_expired(now, now + leeway, leeway) is False
        assert is_token_expired(now, now + leeway + 1, leeway) is True
