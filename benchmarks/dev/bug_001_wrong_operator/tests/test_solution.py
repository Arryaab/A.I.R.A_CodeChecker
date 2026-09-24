from solution import subtract

def test_subtract_pass():
    assert subtract(5, 0) == 5

def test_subtract_fail():
    assert subtract(10, 5) == 5
