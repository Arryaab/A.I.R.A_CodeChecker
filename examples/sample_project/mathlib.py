"""A tiny math library for testing the Aegis runner.

This module intentionally contains one correct function (add)
and one BUGGY function (subtract) so that we can verify the
runner captures both passing and failing tests correctly.
"""


def add(a: int, b: int) -> int:
    """Return the sum of a and b. (Correct implementation.)"""
    return a + b


def subtract(a: int, b: int) -> int:
    """Return a minus b. (BUGGY — uses + instead of -.)"""
    return a + b  # BUG: should be a - b
