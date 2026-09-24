def count_vowels(text):
    vowels = 'aeiou'
    return sum(1 for char in text if char in vowels)
