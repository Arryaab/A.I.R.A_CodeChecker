import pytest
from solution import is_token_expired

def test_token_within_leeway():
    # Expired 30 seconds ago, but leeway is 60 seconds -> Still considered NOT expired
    assert is_token_expired(exp_timestamp=1000, current_timestamp=1030, leeway_seconds=60) is False

def test_token_at_exact_leeway_boundary():
    # Exactly at boundary: current == exp + leeway -> Still NOT expired
    assert is_token_expired(exp_timestamp=1000, current_timestamp=1060, leeway_seconds=60) is False

def test_token_just_beyond_leeway():
    # 1 second past leeway -> EXPIRED
    assert is_token_expired(exp_timestamp=1000, current_timestamp=1061, leeway_seconds=60) is True
