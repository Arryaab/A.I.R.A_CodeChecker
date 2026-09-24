from solution import second_largest

def test_hidden_1():
    assert second_largest([5, 5, 4, 3]) == 4

def test_hidden_2():
    assert second_largest([-1, -5, -3]) == -3
