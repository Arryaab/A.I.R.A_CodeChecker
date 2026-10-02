import pytest
from solution import accumulate_int32, INT32_MAX

def test_positive_overflow_detected():
    with pytest.raises(OverflowError):
        accumulate_int32([INT32_MAX, 1])

def test_within_bounds():
    assert accumulate_int32([100, 200, -50]) == 250
