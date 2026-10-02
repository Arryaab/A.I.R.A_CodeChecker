import pytest
from solution import count_unique_grid_paths

def test_tiny_grid():
    assert count_unique_grid_paths(3, 2) == 3
    assert count_unique_grid_paths(3, 7) == 28
