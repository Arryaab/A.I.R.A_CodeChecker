from solution import generate_worker_seed

def test_distinct_seeds_per_worker():
    s0 = generate_worker_seed(42, 0)
    s1 = generate_worker_seed(42, 1)
    assert s0 != s1
