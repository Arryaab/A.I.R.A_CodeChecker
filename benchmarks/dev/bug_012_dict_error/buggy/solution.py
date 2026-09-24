def word_frequency(text):
    words = text.split()
    freq = {}
    for word in words:
        if word not in freq:
            freq[word] = 1
        else:
            freq[word] = 1
    return freq
