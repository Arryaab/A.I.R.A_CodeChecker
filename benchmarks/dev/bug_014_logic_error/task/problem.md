# Bug 014: Missing Century Exception in Leap Year Calculation

## Description
The `is_leap_year(year)` function only checks `year % 4 == 0`, incorrectly categorizing century years like 1900 as leap years.

## Requirements
- Years divisible by 4 are leap years, except century years (divisible by 100), unless also divisible by 400.
