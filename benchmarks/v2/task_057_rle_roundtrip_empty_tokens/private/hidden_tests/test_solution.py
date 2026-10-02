import pytest
from solution import rle_encode, rle_decode

def test_empty_string_roundtrip():
    assert rle_encode("") == ""
    assert rle_decode("") == ""

def test_single_character():
    orig = "A"
    enc = rle_encode(orig)
    assert rle_decode(enc) == orig

def test_multi_digit_run():
    orig = "X" * 25
    enc = rle_encode(orig)
    assert enc == "X25"
    assert rle_decode(enc) == orig
