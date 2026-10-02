import pytest
import time
from solution import extract_log_severities

def test_large_log_throughput():
    lines = [f"2026-09-27 [{ 'INFO' if i%2==0 else 'ERROR' }] message {i}" for i in range(25000)]
    t0 = time.time()
    res = extract_log_severities(lines)
    elapsed = time.time() - t0
    assert len(res) == 25000
    # Pre-compiled takes < 0.10s, per-line compilation takes > 0.8s
    assert elapsed < 0.25, f"Regex compilation churn: took {elapsed:.2f}s"
