import pytest
from solution import matrix_power

def test_oracle_happy_path_power_zero_is_identity():
    m = [[2.0, 3.0], [4.0, 5.0]]
    expected = [[1.0, 0.0], [0.0, 1.0]]
    assert matrix_power(m, 0) == expected

def test_oracle_boundary_power_zero_3x3():
    m = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
    expected = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ]
    assert matrix_power(m, 0) == expected

def test_oracle_regression_power_one():
    m = [[2.0, 1.0], [0.0, 2.0]]
    assert matrix_power(m, 1) == m
