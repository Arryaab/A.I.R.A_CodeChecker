from solution import second_largest

def test_second_pass():
    assert second_largest([1]) is None

def test_second_fail():
    assert second_largest([1, 2, 3]) == 2
