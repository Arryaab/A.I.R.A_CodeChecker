# Bug 012: Static Count in Word Frequency Map

## Description
The `word_frequency(text)` function sets `freq[word] = 1` even when a word has already been observed.

## Requirements
- Count the frequency of each whitespace-delimited word correctly.
