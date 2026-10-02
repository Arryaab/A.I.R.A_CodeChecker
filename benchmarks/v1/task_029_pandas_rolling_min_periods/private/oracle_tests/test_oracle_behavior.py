import pytest
from solution import rolling_mean

def test_oracle_happy_path_requires_min_periods():
    s = [10.0, None, 20.0, 30.0]
    res = rolling_mean(s, window=3, min_periods=2)
    assert res[0] is None
    assert res[1] is None
    assert res[2] == 15.0
    assert res[3] == 25.0

def test_oracle_happy_path_two_valid():
    s = [10.0, 20.0, 30.0]
    res = rolling_mean(s, window=2, min_periods=2)
    assert res == [None, 15.0, 25.0]

def test_oracle_boundary_all_valid():
    s = [2.0, 4.0]
    res = rolling_mean(s, window=2, min_periods=1)
    assert res == [2.0, 3.0]
