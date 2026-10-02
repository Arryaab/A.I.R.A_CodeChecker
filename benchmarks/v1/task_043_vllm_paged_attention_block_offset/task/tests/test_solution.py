import pytest
from solution import compute_physical_slot

def test_negative_logical_position_raises():
    block_table = [101, 102]
    with pytest.raises(IndexError):
        compute_physical_slot(block_table, logical_pos=-5, block_size=16)
