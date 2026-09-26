from solution import safe_divide

def test_hidden_1():
    assert safe_divide(0, 5) == 0.0

def test_hidden_2():
    assert safe_divide(-10, 2) == -5.0
