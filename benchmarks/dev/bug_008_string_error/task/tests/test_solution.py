from solution import count_vowels

def test_vowels_pass():
    assert count_vowels('hello') == 2

def test_vowels_fail():
    assert count_vowels('HELLO') == 2
