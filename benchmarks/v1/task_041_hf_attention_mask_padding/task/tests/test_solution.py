from solution import build_causal_mask

def test_left_padding_masked():
    # seq_len=3, num_pad=1 (first token is PAD)
    mask = build_causal_mask(seq_len=3, num_pad=1)
    assert mask[0][0] == -1e9
    assert mask[1][0] == -1e9
    assert mask[1][1] == 0.0
