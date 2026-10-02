import pytest
from solution import BloomFilter

def test_basic_bloom_filter():
    bf = BloomFilter(100, 3)
    bf.add("apple")
    assert bf.contains("apple") is True
