from solution import celsius_to_fahrenheit

def test_c2f_pass():
    assert celsius_to_fahrenheit(0) == 32.0

def test_c2f_fail():
    assert celsius_to_fahrenheit(100) == 212.0
