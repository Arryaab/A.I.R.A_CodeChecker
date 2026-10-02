from string_utils import reverse_string, capitalize_words, count_vowels

def test_reverse_string():
    assert reverse_string("hello") == "olleh"

def test_capitalize_words():
    assert capitalize_words("hello world") == "Hello World"

def test_count_vowels_no_u():
    assert count_vowels("hello") == 2

def test_count_vowels():
    # This will fail because 'u' is not counted
    assert count_vowels("umbrella") == 3
