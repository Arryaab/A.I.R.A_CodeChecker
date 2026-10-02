import pytest
from solution import dequantize_weights

def test_oracle_happy_path_scaling():
    q = [10, -5, 0]
    res = dequantize_weights(q, 0.02)
    assert abs(res[0] - 0.2) < 1e-5
    assert abs(res[1] - (-0.1)) < 1e-5
    assert res[2] == 0.0

def test_oracle_fractional_precision():
    q = [3]
    res = dequantize_weights(q, 0.1)
    assert abs(res[0] - 0.3) < 1e-5

def test_oracle_boundary_empty():
    assert dequantize_weights([], 0.5) == []
