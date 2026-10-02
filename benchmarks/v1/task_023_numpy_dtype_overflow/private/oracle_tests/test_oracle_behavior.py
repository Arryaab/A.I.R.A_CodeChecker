import pytest
from solution import accumulate_int32, INT32_MAX, INT32_MIN

def test_oracle_happy_path_within_bounds():
    assert accumulate_int32([100, 200, 300]) == 600
    assert accumulate_int32([-100, -200, 50]) == -250

def test_oracle_negative_positive_overflow():
    with pytest.raises(OverflowError, match="32-bit integer overflow"):
        accumulate_int32([INT32_MAX, 1])

def test_oracle_negative_negative_overflow():
    with pytest.raises(OverflowError, match="32-bit integer overflow"):
        accumulate_int32([INT32_MIN, -1])

def test_oracle_boundary_exact_limits():
    assert accumulate_int32([INT32_MAX]) == INT32_MAX
    assert accumulate_int32([INT32_MIN]) == INT32_MIN
