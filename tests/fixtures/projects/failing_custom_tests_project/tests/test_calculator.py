from calculator import Calculator

def test_add():
    c = Calculator()
    assert c.add(2, 3) == 5

def test_subtract():
    c = Calculator()
    assert c.subtract(5, 3) == 2
