import pytest
from solution import build_causal_mask

def test_oracle_happy_path_left_padded():
    mask = build_causal_mask(seq_len=3, num_pad=1)
    assert mask[0][0] == -1e9
    assert mask[1][0] == -1e9
    assert mask[1][1] == 0.0

def test_oracle_boundary_no_pad():
    mask = build_causal_mask(seq_len=2, num_pad=0)
    assert mask[0][0] == 0.0
    assert mask[0][1] == -1e9
    assert mask[1][0] == 0.0
    assert mask[1][1] == 0.0

def test_oracle_invariants_future_tokens_masked():
    mask = build_causal_mask(seq_len=4, num_pad=1)
    for i in range(4):
        for j in range(i + 1, 4):
            assert mask[i][j] == -1e9
