def reverse_string(s):
    return s[::-1]

def capitalize_words(s):
    return " ".join(word.capitalize() for word in s.split())

def count_vowels(s):
    # Intentional bug: 'u' is missing
    vowels = 'aeioAEIO'
    return sum(1 for char in s if char in vowels)
