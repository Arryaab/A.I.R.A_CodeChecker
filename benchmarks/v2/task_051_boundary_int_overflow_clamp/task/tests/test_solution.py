import pytest
from solution import clamp_range

def test_clamp_within_range():
    assert clamp_range(5, 0, 10) == 5

def test_clamp_below_range():
    assert clamp_range(-5, 0, 10) == 0

def test_clamp_invalid_bounds():
    with pytest.raises(ValueError):
        clamp_range(5, 10, 0)
