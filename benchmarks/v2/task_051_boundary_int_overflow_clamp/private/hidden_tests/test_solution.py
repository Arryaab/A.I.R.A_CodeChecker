import pytest
from solution import clamp_range

def test_clamp_exact_high_boundary():
    assert clamp_range(10, 0, 10) == 10

def test_clamp_above_high():
    assert clamp_range(15, 0, 10) == 10

def test_clamp_identical_bounds():
    assert clamp_range(5, 5, 5) == 5
    assert clamp_range(0, 5, 5) == 5
    assert clamp_range(10, 5, 5) == 5
