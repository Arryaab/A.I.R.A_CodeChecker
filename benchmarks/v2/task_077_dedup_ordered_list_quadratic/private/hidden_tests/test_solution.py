import pytest
import time
from solution import deduplicate_preserve_order

def test_large_list_dedup_performance():
    # 20,000 integers with repeats
    data = [i % 500 for i in range(20000)]
    t0 = time.time()
    res = deduplicate_preserve_order(data)
    elapsed = time.time() - t0
    assert len(res) == 500
    assert res[:5] == [0, 1, 2, 3, 4]
    # Set-based dedup takes < 0.05s, list membership takes > 0.8s
    assert elapsed < 0.20, f"Quadratic dedup latency: took {elapsed:.2f}s"
