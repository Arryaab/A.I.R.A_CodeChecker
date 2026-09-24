from solution import max_of_three

def test_hidden_1():
    assert max_of_three(5, 5, 5) == 5

def test_hidden_2():
    assert max_of_three(-1, -5, 0) == 0
