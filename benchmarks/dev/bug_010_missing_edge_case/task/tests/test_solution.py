from solution import safe_divide

def test_div_pass():
    assert safe_divide(10, 2) == 5.0

def test_div_fail():
    assert safe_divide(10, 0) is None
