from solution import build_causal_mask

def test_future_tokens_masked():
    mask = build_causal_mask(seq_len=3, num_pad=0)
    assert mask[0][1] == -1e9
    assert mask[0][0] == 0.0
