from solution import first_positive

def test_hidden_1():
    assert first_positive([-1, -2, -3]) is None

def test_hidden_2():
    assert first_positive([-1, 5, 3]) == 5
