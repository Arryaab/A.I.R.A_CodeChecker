from solution import first_positive

def test_first_pass():
    assert first_positive([1, -2, 3]) == 1

def test_first_fail():
    assert first_positive([]) is None
