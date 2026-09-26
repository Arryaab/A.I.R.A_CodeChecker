# Bug 005: Incorrect Variable in Temperature Conversion Formula

## Description
The `celsius_to_fahrenheit(celsius)` function uses a hardcoded `c = 0` variable instead of the input `celsius` parameter.

## Requirements
- Convert `celsius` to Fahrenheit using `(celsius * 9/5) + 32`.
