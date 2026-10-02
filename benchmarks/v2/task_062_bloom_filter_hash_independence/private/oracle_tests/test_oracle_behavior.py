import pytest
from solution import BloomFilter

def test_oracle_false_positive_rate():
    bf = BloomFilter(5000, 5)
    for i in range(100):
        bf.add(f"item_{i}")
    for i in range(100):
        assert bf.contains(f"item_{i}") is True
    # Negative queries should have low false positive rate (< 10%)
    fp = sum(1 for i in range(100, 300) if bf.contains(f"item_{i}"))
    assert fp < 20
