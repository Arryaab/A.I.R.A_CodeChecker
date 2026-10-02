import pytest
from solution import rle_encode, rle_decode

def test_basic_rle():
    orig = "AAAAABBBCC"
    encoded = rle_encode(orig)
    assert encoded == "A5B3C2"
    assert rle_decode(encoded) == orig
