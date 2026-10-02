import pytest
import time
from solution import count_unique_grid_paths

def test_moderate_grid_fast():
    t0 = time.time()
    ans = count_unique_grid_paths(18, 18)
    elapsed = time.time() - t0
    assert ans == 2333606220
    # Exponential recursion would take > 60s, closed-form takes < 0.01s
    assert elapsed < 0.20, f"Combinatorial explosion: took {elapsed:.2f}s"
