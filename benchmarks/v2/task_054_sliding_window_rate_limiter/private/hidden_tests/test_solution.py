import pytest
from solution import SlidingWindowRateLimiter

def test_exact_window_boundary_retained():
    # Max 2 requests in 10s window
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=10.0)
    assert limiter.allow_request("user1", 10.0) is True
    assert limiter.allow_request("user1", 15.0) is True
    # At timestamp 20.0, the request at 10.0 is exactly 10.0s old (20 - 10 = 10 == cutoff).
    # Since window is [cutoff, timestamp], 10.0 is within the window.
    # Therefore, 2 requests are active, so third request at 20.0 must be BLOCKED.
    assert limiter.allow_request("user1", 20.0) is False

def test_request_expires_after_boundary():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=10.0)
    assert limiter.allow_request("user1", 10.0) is True
    assert limiter.allow_request("user1", 15.0) is True
    # At 20.1, the 10.0 request is 10.1s old (> 10s), so it expires.
    assert limiter.allow_request("user1", 20.1) is True
