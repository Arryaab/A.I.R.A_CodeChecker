import pytest
from solution import constant_time_compare

def test_oracle_happy_path_equal():
    assert constant_time_compare(b"hash123", b"hash123") is True

def test_oracle_negative_same_first_byte_diff_remainder():
    # Both start with 'h' and have same length; buggy returns True
    assert constant_time_compare(b"hash123", b"hash456") is False

def test_oracle_negative_differ_last_byte():
    assert constant_time_compare(b"key_a", b"key_b") is False

def test_oracle_negative_different_lengths():
    assert constant_time_compare(b"short", b"longer_string") is False

def test_oracle_boundary_empty_bytes():
    assert constant_time_compare(b"", b"") is True
    assert constant_time_compare(b"", b"a") is False
