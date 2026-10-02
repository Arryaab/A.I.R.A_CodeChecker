def compute_physical_slot(block_table: list[int], logical_pos: int, block_size: int = 16) -> tuple[int, int]:
    # BUG: does not guard against negative logical position
    block_idx = logical_pos // block_size
    offset = logical_pos % block_size
    physical_block = block_table[block_idx]
    return physical_block, offset
