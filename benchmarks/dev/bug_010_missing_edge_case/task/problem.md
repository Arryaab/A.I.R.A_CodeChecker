# Bug 010: ZeroDivisionError Handling in Safe Division

## Description
The `safe_divide(a, b)` function does not check for `b == 0`, crashing with a `ZeroDivisionError`.

## Requirements
- Return `None` when `b == 0`.
- Otherwise return `a / b`.
