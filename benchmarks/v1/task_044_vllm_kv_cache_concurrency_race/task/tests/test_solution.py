from solution import BlockAllocator

def test_shared_block_not_freed_until_zero_refs():
    alloc = BlockAllocator(num_blocks=2)
    b = alloc.allocate()
    alloc.share(b)  # 2 references (e.g. beam search or prefix cache)
    alloc.free(b)
    assert b not in alloc.free_blocks
    alloc.free(b)
    assert b in alloc.free_blocks
