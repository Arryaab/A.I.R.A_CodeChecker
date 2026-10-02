import pytest
from solution import parse_int_range

def test_out_of_bounds_raises():
    with pytest.raises(ValueError):
        parse_int_range("9", 10, 20)
    with pytest.raises(ValueError):
        parse_int_range("21", 10, 20)
