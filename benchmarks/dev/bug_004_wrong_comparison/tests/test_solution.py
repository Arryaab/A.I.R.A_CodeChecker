from solution import max_of_three

def test_max_pass():
    assert max_of_three(1, 5, 2) == 5

def test_max_fail():
    assert max_of_three(1, 2, 5) == 5
