import pytest
from solution import deduplicate_preserve_order

def test_small_dedup():
    assert deduplicate_preserve_order([3, 1, 2, 3, 1, 4]) == [3, 1, 2, 4]
