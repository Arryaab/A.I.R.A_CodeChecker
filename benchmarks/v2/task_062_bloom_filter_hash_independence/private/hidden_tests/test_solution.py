import pytest
from solution import BloomFilter

def test_hash_dispersion_independence():
    bf = BloomFilter(1024, 4)
    hashes = bf._get_hashes("test_string")
    assert len(set(hashes)) == 4
    # With linear addition, consecutive elements have fixed delta 1
    # Independent hashes should not have a trivial constant step
    steps = [hashes[i+1] - hashes[i] for i in range(len(hashes)-1)]
    assert len(set(steps)) > 1 or abs(steps[0]) > 5
