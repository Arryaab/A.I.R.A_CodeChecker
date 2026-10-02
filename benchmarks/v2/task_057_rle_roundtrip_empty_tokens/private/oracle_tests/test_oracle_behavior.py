import pytest
from solution import rle_encode, rle_decode

def test_oracle_random_roundtrip_properties():
    cases = ["", "A", "AB", "AAAAA", "A" * 15 + "B" * 20]
    for c in cases:
        assert rle_decode(rle_encode(c)) == c
