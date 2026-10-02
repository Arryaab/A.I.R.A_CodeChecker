import pytest
from solution import compute_sliding_window_shape

def test_oracle_happy_path_standard_sliding_window():
    assert compute_sliding_window_shape(10, 3, 1) == (8, 3)
    assert compute_sliding_window_shape(10, 2, 2) == (5, 2)
    assert compute_sliding_window_shape(7, 3, 2) == (3, 3)

def test_oracle_boundary_window_equals_length():
    assert compute_sliding_window_shape(5, 5, 1) == (1, 5)

def test_oracle_boundary_window_exceeds_length():
    assert compute_sliding_window_shape(3, 5, 1) == (0, 0)

def test_oracle_boundary_invalid_window_size():
    assert compute_sliding_window_shape(10, 0, 1) == (0, 0)
    assert compute_sliding_window_shape(10, -1, 1) == (0, 0)

def test_oracle_adversarial_step_larger_than_window():
    assert compute_sliding_window_shape(10, 2, 5) == (2, 2)
