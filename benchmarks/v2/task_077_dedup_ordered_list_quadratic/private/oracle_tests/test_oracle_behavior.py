import pytest
from solution import deduplicate_preserve_order

def test_oracle_empty_and_uniform():
    assert deduplicate_preserve_order([]) == []
    assert deduplicate_preserve_order([7, 7, 7, 7]) == [7]
