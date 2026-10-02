class BlockAllocator:
    def __init__(self, num_blocks=10):
        self.free_blocks = set(range(num_blocks))
        self.ref_counts = {i: 0 for i in range(num_blocks)}

    def allocate(self) -> int:
        if not self.free_blocks:
            raise RuntimeError("Out of blocks")
        b = self.free_blocks.pop()
        self.ref_counts[b] = 1
        return b

    def free(self, block_id: int):
        # BUG: immediately reclaims block to free_blocks without checking ref_counts
        self.ref_counts[block_id] -= 1
        self.free_blocks.add(block_id)
