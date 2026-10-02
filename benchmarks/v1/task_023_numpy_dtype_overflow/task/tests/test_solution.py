import pytest
from solution import accumulate_int32, INT32_MIN

def test_negative_overflow_detected():
    with pytest.raises(OverflowError):
        accumulate_int32([INT32_MIN, -1])
