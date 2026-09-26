from solution import flatten

def test_flatten_pass():
    assert flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4]

def test_flatten_fail():
    assert flatten([[1, 2], (3, 4)]) == [1, 2, 3, 4]
