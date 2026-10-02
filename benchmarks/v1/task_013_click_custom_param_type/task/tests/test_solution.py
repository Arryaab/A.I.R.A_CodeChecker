from solution import parse_int_range

def test_exact_bounds_allowed():
    assert parse_int_range("10", 10, 20) == 10
    assert parse_int_range("20", 10, 20) == 20
