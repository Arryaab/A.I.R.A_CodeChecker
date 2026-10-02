import pytest
from solution import BlockAllocator

def test_oracle_happy_path_shared_block_refcount():
    alloc = BlockAllocator(num_blocks=2)
    b = alloc.allocate()
    alloc.share(b)
    alloc.free(b)
    assert b not in alloc.free_blocks
    alloc.free(b)
    assert b in alloc.free_blocks

def test_oracle_boundary_single_alloc_free():
    alloc = BlockAllocator(num_blocks=1)
    b = alloc.allocate()
    assert len(alloc.free_blocks) == 0
    alloc.free(b)
    assert len(alloc.free_blocks) == 1

def test_oracle_negative_out_of_blocks():
    alloc = BlockAllocator(num_blocks=1)
    alloc.allocate()
    with pytest.raises(RuntimeError, match="Out of blocks"):
        alloc.allocate()
