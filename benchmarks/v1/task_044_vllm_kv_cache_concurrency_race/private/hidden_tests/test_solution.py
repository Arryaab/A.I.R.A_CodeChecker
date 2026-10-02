from solution import BlockAllocator

def test_basic_allocation_and_free():
    alloc = BlockAllocator(num_blocks=1)
    b = alloc.allocate()
    assert len(alloc.free_blocks) == 0
    alloc.free(b)
    assert len(alloc.free_blocks) == 1
