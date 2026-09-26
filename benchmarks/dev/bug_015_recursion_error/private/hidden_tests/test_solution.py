from solution import flatten

def test_hidden_1():
    assert flatten([1, [2, [3, (4, 5)]]]) == [1, 2, 3, 4, 5]

def test_hidden_2():
    assert flatten([]) == []
