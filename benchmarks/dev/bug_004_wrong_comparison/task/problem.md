# Bug 004: Inverted Comparison Operator in Maximum Calculation

## Description
The `max_of_three(a, b, c)` function attempts to find the maximum of three numbers, but compares `c < max_val` instead of `c > max_val`.

## Requirements
- Return the highest value among `a`, `b`, and `c`.
