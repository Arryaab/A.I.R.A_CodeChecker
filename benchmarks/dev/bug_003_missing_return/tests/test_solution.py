from solution import is_even

def test_is_even_pass():
    assert is_even(2) is True

def test_is_even_fail():
    assert is_even(3) is False
