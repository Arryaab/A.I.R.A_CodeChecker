# Bug 013: IndexError on Empty Input List in First Positive Finder

## Description
The `first_positive(numbers)` function inspects `numbers[0]` unconditionally, raising `IndexError` on empty lists.

## Requirements
- Return the first integer `> 0`.
- Return `None` if the list is empty or contains no positive numbers.
