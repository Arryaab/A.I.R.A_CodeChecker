from solution import generate_worker_seed

def test_deterministic_reproducibility():
    assert generate_worker_seed(100, 3) == generate_worker_seed(100, 3)
