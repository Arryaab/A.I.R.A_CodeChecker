import pytest
from solution import clip_array

def test_oracle_happy_path_clipping():
    arr = [-10.0, 0.0, 5.0, 10.0, 20.0]
    res = clip_array(arr, a_min=0.0, a_max=10.0)
    assert res == [0.0, 0.0, 5.0, 10.0, 10.0]

def test_oracle_boundary_all_within_bounds():
    arr = [1.0, 2.0, 3.0]
    assert clip_array(arr, 0.0, 5.0) == [1.0, 2.0, 3.0]

def test_oracle_boundary_all_below_min():
    arr = [-5.0, -10.0]
    assert clip_array(arr, 0.0, 10.0) == [0.0, 0.0]
