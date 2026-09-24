"""Tests for the sample mathlib module.

test_add should PASS (add is correct).
test_subtract should FAIL (subtract has a bug).

This gives us a controlled scenario to verify that the
Aegis runner correctly captures both outcomes.
"""

from mathlib import add, subtract


def test_add():
    """This test should PASS — add(2, 3) returns 5."""
    assert add(2, 3) == 5


def test_subtract():
    """This test should FAIL — subtract uses + instead of -.

    subtract(10, 3) returns 13 (bug), but we expect 7.
    """
    assert subtract(10, 3) == 7
