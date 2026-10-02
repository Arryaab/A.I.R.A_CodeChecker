from solution import compute_physical_slot

def test_valid_physical_slot_mapping():
    block_table = [200, 201]
    p_block, offset = compute_physical_slot(block_table, logical_pos=18, block_size=16)
    assert p_block == 201
    assert offset == 2
