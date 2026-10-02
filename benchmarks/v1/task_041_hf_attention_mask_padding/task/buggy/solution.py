def build_causal_mask(seq_len: int, num_pad: int) -> list[list[float]]:
    # BUG: fails to mask out padded columns on the left
    mask = [[0.0] * seq_len for _ in range(seq_len)]
    for i in range(seq_len):
        for j in range(seq_len):
            if j > i:
                mask[i][j] = -1e9
    return mask
