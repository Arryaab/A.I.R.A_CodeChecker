import pytest
from solution import SlidingWindowRateLimiter

def test_oracle_client_isolation():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=5.0)
    assert limiter.allow_request("c1", 10.0) is True
    assert limiter.allow_request("c2", 10.0) is True
    assert limiter.allow_request("c1", 12.0) is False
    assert limiter.allow_request("c2", 12.0) is False
