import pytest
from solution import count_unique_grid_paths

def test_oracle_boundary_dimensions():
    assert count_unique_grid_paths(1, 100) == 1
    assert count_unique_grid_paths(100, 1) == 1
    assert count_unique_grid_paths(0, 5) == 0
