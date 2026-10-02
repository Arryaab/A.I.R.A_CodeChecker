import pytest
from solution import parse_int_range

def test_oracle_happy_path_endpoints():
    assert parse_int_range("10", 10, 20) == 10
    assert parse_int_range("20", 10, 20) == 20
    assert parse_int_range("15", 10, 20) == 15

def test_oracle_negative_strictly_below():
    with pytest.raises(ValueError, match="out of range"):
        parse_int_range("9", 10, 20)

def test_oracle_negative_strictly_above():
    with pytest.raises(ValueError, match="out of range"):
        parse_int_range("21", 10, 20)

def test_oracle_boundary_negative_numbers():
    assert parse_int_range("-5", -10, -5) == -5
    with pytest.raises(ValueError):
        parse_int_range("-4", -10, -5)
