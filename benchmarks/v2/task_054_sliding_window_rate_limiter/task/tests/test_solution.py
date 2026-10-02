import pytest
from solution import SlidingWindowRateLimiter

def test_rate_limiter_allows_under_limit():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10.0)
    assert limiter.allow_request("user1", 1.0) is True
    assert limiter.allow_request("user1", 2.0) is True
    assert limiter.allow_request("user1", 3.0) is True

def test_rate_limiter_blocks_over_limit():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=10.0)
    assert limiter.allow_request("user1", 1.0) is True
    assert limiter.allow_request("user1", 2.0) is True
    assert limiter.allow_request("user1", 3.0) is False
