import pytest
from solution import generate_worker_seed

def test_oracle_happy_path_workers_have_distinct_seeds():
    base = 42
    s0 = generate_worker_seed(base, worker_id=0)
    s1 = generate_worker_seed(base, worker_id=1)
    s2 = generate_worker_seed(base, worker_id=2)
    assert len({s0, s1, s2}) == 3

def test_oracle_invariant_determinism():
    assert generate_worker_seed(100, 3) == generate_worker_seed(100, 3)

def test_oracle_boundary_fits_31_bit_int():
    for w in range(10):
        s = generate_worker_seed(2**31 - 2, w)
        assert 0 <= s < 2**31 - 1
