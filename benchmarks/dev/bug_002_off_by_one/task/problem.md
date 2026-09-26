# Bug 002: Off-by-one Boundary in Range Sum

## Description
The `range_sum(start, end)` function is intended to compute the inclusive sum from `start` to `end` inclusive, but omits the end boundary.

## Requirements
- Return the sum of all integers from `start` to `end` inclusive.
- If `start > end`, return `0`.
