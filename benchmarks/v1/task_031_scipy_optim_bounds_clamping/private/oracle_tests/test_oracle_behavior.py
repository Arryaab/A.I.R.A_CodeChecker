import pytest
from solution import project_box_bounds

def test_oracle_happy_path_clamping():
    x = [-2.0, 1.5, 5.0]
    bounds = [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]
    assert project_box_bounds(x, bounds) == [0.0, 1.5, 3.0]

def test_oracle_boundary_exact_limits():
    x = [0.0, 2.0]
    bounds = [(0.0, 2.0), (0.0, 2.0)]
    assert project_box_bounds(x, bounds) == [0.0, 2.0]

def test_oracle_boundary_all_interior():
    x = [1.0, 1.0]
    bounds = [(0.0, 5.0), (0.0, 5.0)]
    assert project_box_bounds(x, bounds) == [1.0, 1.0]
