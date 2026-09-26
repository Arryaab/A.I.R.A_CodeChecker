from solution import is_leap_year

def test_leap_pass():
    assert is_leap_year(2004) is True

def test_leap_fail():
    assert is_leap_year(1900) is False
