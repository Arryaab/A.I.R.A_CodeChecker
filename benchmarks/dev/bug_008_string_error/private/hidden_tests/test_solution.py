from solution import count_vowels

def test_hidden_1():
    assert count_vowels('AeIoU') == 5

def test_hidden_2():
    assert count_vowels('xyz') == 0
