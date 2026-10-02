import pytest
import time
from solution import has_required_permissions

def test_large_permission_set_performance():
    assigned = [f"role_{i}" for i in range(15000)]
    required = [f"role_{i}" for i in range(5000)]
    t0 = time.time()
    res = has_required_permissions(assigned, required)
    elapsed = time.time() - t0
    assert res is True
    # Set lookup takes < 0.05s, list scans take > 1.0s
    assert elapsed < 0.20, f"Unindexed lookup latency bottleneck: took {elapsed:.2f}s"
