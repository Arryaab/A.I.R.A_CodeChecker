from solution import word_frequency

def test_hidden_1():
    assert word_frequency('') == {}

def test_hidden_2():
    assert word_frequency('a a a b b') == {'a': 3, 'b': 2}
