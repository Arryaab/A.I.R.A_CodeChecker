import pytest
from solution import compute_physical_slot

def test_oracle_happy_path_slot_lookup():
    block_table = [101, 102]
    phys_block, offset = compute_physical_slot(block_table, logical_pos=20, block_size=16)
    assert phys_block == 102
    assert offset == 4

def test_oracle_negative_negative_logical_pos():
    with pytest.raises(IndexError):
        compute_physical_slot([101], logical_pos=-1, block_size=16)

def test_oracle_negative_unallocated_block():
    with pytest.raises(IndexError):
        compute_physical_slot([101], logical_pos=32, block_size=16)

def test_oracle_negative_invalid_block_size():
    with pytest.raises(ValueError):
        compute_physical_slot([101], logical_pos=0, block_size=0)
