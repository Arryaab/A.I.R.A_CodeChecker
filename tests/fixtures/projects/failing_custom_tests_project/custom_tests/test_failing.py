from calculator import Calculator

def test_custom_failing():
    c = Calculator()
    assert c.add(1, 1) == 999  # Intentionally failing custom test
