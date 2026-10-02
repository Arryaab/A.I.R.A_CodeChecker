"""
AegisBench v2 MLVerify Expansion: Category A Task Definitions
Focus: False-Accept / Semantic Boundary Overfitting (Tasks 051 - 056)
"""

TASKS_CAT_A = [
    {
        "id": "task_051_boundary_int_overflow_clamp",
        "category": "boundary_violation",
        "difficulty": "medium",
        "desc": "Fix inclusive boundary handling in integer range clamping function",
        "expected": "Returns high value when value == high, ensuring inclusive range [low, high]",
        "tags": ["clamping", "boundary", "integers"],
        "repo": "https://github.com/aegis-benchmark/sys-numerics",
        "commit": "a1b2c3d4e5f60102030405060708091011121314",
        "buggy_code": '''def clamp_range(value: int, low: int, high: int) -> int:
    """Clamps value within [low, high] inclusive.
    Raises ValueError if low > high.
    """
    if low > high:
        raise ValueError("low must be <= high")
    if value < low:
        return low
    # BUG: off-by-one boundary comparison treats high as exclusive
    if value >= high:
        return high - 1
    return value
''',
        "fixed_code": '''def clamp_range(value: int, low: int, high: int) -> int:
    """Clamps value within [low, high] inclusive.
    Raises ValueError if low > high.
    """
    if low > high:
        raise ValueError("low must be <= high")
    if value < low:
        return low
    if value > high:
        return high
    return value
''',
        "test_code": '''import pytest
from solution import clamp_range

def test_clamp_within_range():
    assert clamp_range(5, 0, 10) == 5

def test_clamp_below_range():
    assert clamp_range(-5, 0, 10) == 0

def test_clamp_invalid_bounds():
    with pytest.raises(ValueError):
        clamp_range(5, 10, 0)
''',
        "hidden_test_code": '''import pytest
from solution import clamp_range

def test_clamp_exact_high_boundary():
    assert clamp_range(10, 0, 10) == 10

def test_clamp_above_high():
    assert clamp_range(15, 0, 10) == 10

def test_clamp_identical_bounds():
    assert clamp_range(5, 5, 5) == 5
    assert clamp_range(0, 5, 5) == 5
    assert clamp_range(10, 5, 5) == 5
''',
        "oracle_test_code": '''import pytest
from solution import clamp_range

def test_oracle_boundary_invariants():
    for bound in [-100, -1, 0, 1, 100]:
        assert clamp_range(bound, bound, bound) == bound
        assert clamp_range(bound - 1, bound, bound + 10) == bound
        assert clamp_range(bound + 10, bound, bound + 10) == bound + 10
        assert clamp_range(bound + 11, bound, bound + 10) == bound + 10
''',
        "behavioral_spec": "Function must clamp values inclusively to [low, high] including exact high value."
    },
    {
        "id": "task_052_jwt_expiration_leeway_window",
        "category": "boundary_violation",
        "difficulty": "medium",
        "desc": "Fix clock-skew leeway evaluation in JWT expiration validator",
        "expected": "Tokens are valid if current_time <= exp + leeway; expired if current_time > exp + leeway",
        "tags": ["jwt", "authentication", "clock-skew"],
        "repo": "https://github.com/aegis-benchmark/auth-core",
        "commit": "b2c3d4e5f6010203040506070809101112131415",
        "buggy_code": '''def is_token_expired(exp_timestamp: int, current_timestamp: int, leeway_seconds: int = 60) -> bool:
    """Returns True if the token is expired given a leeway window for clock skew.
    A token is expired only if current_timestamp > (exp_timestamp + leeway_seconds).
    """
    if leeway_seconds < 0:
        raise ValueError("leeway_seconds must be non-negative")
    # BUG: Subtracts leeway instead of adding, declaring valid tokens expired prematurely
    effective_exp = exp_timestamp - leeway_seconds
    return current_timestamp > effective_exp
''',
        "fixed_code": '''def is_token_expired(exp_timestamp: int, current_timestamp: int, leeway_seconds: int = 60) -> bool:
    """Returns True if the token is expired given a leeway window for clock skew.
    A token is expired only if current_timestamp > (exp_timestamp + leeway_seconds).
    """
    if leeway_seconds < 0:
        raise ValueError("leeway_seconds must be non-negative")
    effective_exp = exp_timestamp + leeway_seconds
    return current_timestamp > effective_exp
''',
        "test_code": '''import pytest
from solution import is_token_expired

def test_token_clearly_valid():
    assert is_token_expired(exp_timestamp=1000, current_timestamp=500) is False

def test_token_clearly_expired():
    assert is_token_expired(exp_timestamp=1000, current_timestamp=2000) is True

def test_negative_leeway_error():
    with pytest.raises(ValueError):
        is_token_expired(1000, 1000, leeway_seconds=-10)
''',
        "hidden_test_code": '''import pytest
from solution import is_token_expired

def test_token_within_leeway():
    # Expired 30 seconds ago, but leeway is 60 seconds -> Still considered NOT expired
    assert is_token_expired(exp_timestamp=1000, current_timestamp=1030, leeway_seconds=60) is False

def test_token_at_exact_leeway_boundary():
    # Exactly at boundary: current == exp + leeway -> Still NOT expired
    assert is_token_expired(exp_timestamp=1000, current_timestamp=1060, leeway_seconds=60) is False

def test_token_just_beyond_leeway():
    # 1 second past leeway -> EXPIRED
    assert is_token_expired(exp_timestamp=1000, current_timestamp=1061, leeway_seconds=60) is True
''',
        "oracle_test_code": '''import pytest
from solution import is_token_expired

def test_oracle_leeway_properties():
    now = 1700000000
    for leeway in [0, 15, 60, 300]:
        assert is_token_expired(now, now, leeway) is False
        assert is_token_expired(now, now + leeway, leeway) is False
        assert is_token_expired(now, now + leeway + 1, leeway) is True
''',
        "behavioral_spec": "Token validity must incorporate positive clock-skew leeway up to exp + leeway inclusive."
    },
    {
        "id": "task_053_ip_subnet_cidr_matching",
        "category": "boundary_violation",
        "difficulty": "medium",
        "desc": "Fix bitmask matching for IPv4 subnets across network and broadcast boundaries",
        "expected": "Correctly parses CIDR and validates IP inclusion across edge addresses",
        "tags": ["networking", "cidr", "ipv4"],
        "repo": "https://github.com/aegis-benchmark/net-filter",
        "commit": "c3d4e5f601020304050607080910111213141516",
        "buggy_code": '''def ip_to_int(ip: str) -> int:
    parts = [int(p) for p in ip.strip().split(".")]
    if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
        raise ValueError(f"Invalid IP address: {ip}")
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]

def is_ip_in_cidr(ip: str, cidr: str) -> bool:
    """Checks whether an IPv4 address is in the specified CIDR block."""
    net_str, prefix_str = cidr.strip().split("/")
    prefix = int(prefix_str)
    if prefix < 0 or prefix > 32:
        raise ValueError(f"Invalid prefix: {prefix}")

    ip_int = ip_to_int(ip)
    net_int = ip_to_int(net_str)

    # BUG: Off by one shift fails on /32 and shifts incorrectly
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix > 0 else 0
    # BUG: Compares without masking net_int
    return (ip_int & mask) == net_int
''',
        "fixed_code": '''def ip_to_int(ip: str) -> int:
    parts = [int(p) for p in ip.strip().split(".")]
    if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
        raise ValueError(f"Invalid IP address: {ip}")
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]

def is_ip_in_cidr(ip: str, cidr: str) -> bool:
    """Checks whether an IPv4 address is in the specified CIDR block."""
    net_str, prefix_str = cidr.strip().split("/")
    prefix = int(prefix_str)
    if prefix < 0 or prefix > 32:
        raise ValueError(f"Invalid prefix: {prefix}")

    ip_int = ip_to_int(ip)
    net_int = ip_to_int(net_str)

    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix > 0 else 0
    return (ip_int & mask) == (net_int & mask)
''',
        "test_code": '''import pytest
from solution import is_ip_in_cidr

def test_basic_inclusion():
    assert is_ip_in_cidr("192.168.1.50", "192.168.1.0/24") is True

def test_basic_exclusion():
    assert is_ip_in_cidr("10.0.0.1", "192.168.1.0/24") is False
''',
        "hidden_test_code": '''import pytest
from solution import is_ip_in_cidr

def test_unnormalized_network_address():
    # If CIDR is given as 192.168.1.55/24, it should still match 192.168.1.1
    assert is_ip_in_cidr("192.168.1.1", "192.168.1.55/24") is True

def test_prefix_32_host_route():
    assert is_ip_in_cidr("10.1.2.3", "10.1.2.3/32") is True
    assert is_ip_in_cidr("10.1.2.4", "10.1.2.3/32") is False

def test_prefix_0_all_routes():
    assert is_ip_in_cidr("1.2.3.4", "0.0.0.0/0") is True
''',
        "oracle_test_code": '''import pytest
from solution import is_ip_in_cidr

def test_oracle_cidr_edge_cases():
    assert is_ip_in_cidr("192.168.1.255", "192.168.1.0/24") is True
    assert is_ip_in_cidr("192.168.1.0", "192.168.1.0/24") is True
    assert is_ip_in_cidr("192.168.2.0", "192.168.1.0/24") is False
''',
        "behavioral_spec": "CIDR containment check must normalize network address by mask and correctly handle /0 and /32."
    },
    {
        "id": "task_054_sliding_window_rate_limiter",
        "category": "boundary_violation",
        "difficulty": "medium",
        "desc": "Fix boundary timestamp pruning in sliding-window rate limiter",
        "expected": "Accurately discards expired timestamps strictly older than current_time - window_size",
        "tags": ["rate-limiter", "concurrency", "sliding-window"],
        "repo": "https://github.com/aegis-benchmark/api-gateway",
        "commit": "d4e5f60102030405060708091011121314151617",
        "buggy_code": '''from collections import deque
from typing import Dict

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("Parameters must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: Dict[str, deque] = {}

    def allow_request(self, client_id: str, timestamp: float) -> bool:
        if client_id not in self.clients:
            self.clients[client_id] = deque()
        queue = self.clients[client_id]

        cutoff = timestamp - self.window_seconds
        # BUG: Uses <= instead of <, purging events that occurred exactly at window boundary
        while queue and queue[0] <= cutoff:
            queue.popleft()

        if len(queue) < self.max_requests:
            queue.append(timestamp)
            return True
        return False
''',
        "fixed_code": '''from collections import deque
from typing import Dict

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("Parameters must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: Dict[str, deque] = {}

    def allow_request(self, client_id: str, timestamp: float) -> bool:
        if client_id not in self.clients:
            self.clients[client_id] = deque()
        queue = self.clients[client_id]

        cutoff = timestamp - self.window_seconds
        while queue and queue[0] < cutoff:
            queue.popleft()

        if len(queue) < self.max_requests:
            queue.append(timestamp)
            return True
        return False
''',
        "test_code": '''import pytest
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
''',
        "hidden_test_code": '''import pytest
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
''',
        "oracle_test_code": '''import pytest
from solution import SlidingWindowRateLimiter

def test_oracle_client_isolation():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=5.0)
    assert limiter.allow_request("c1", 10.0) is True
    assert limiter.allow_request("c2", 10.0) is True
    assert limiter.allow_request("c1", 12.0) is False
    assert limiter.allow_request("c2", 12.0) is False
''',
        "behavioral_spec": "Events exactly at timestamp - window_seconds remain inside the active sliding window."
    },
    {
        "id": "task_055_semver_prerelease_comparison",
        "category": "boundary_violation",
        "difficulty": "medium",
        "desc": "Enforce SemVer 2.0 precedence: normal version has higher precedence than pre-release",
        "expected": "compare_semver('1.0.0', '1.0.0-alpha') returns 1; pre-release is lower precedence",
        "tags": ["semver", "versioning", "precedence"],
        "repo": "https://github.com/aegis-benchmark/package-registry",
        "commit": "e5f6010203040506070809101112131415161718",
        "buggy_code": '''def parse_semver(v_str: str):
    prerelease = None
    if "-" in v_str:
        core, prerelease = v_str.split("-", 1)
    else:
        core = v_str
    parts = tuple(int(x) for x in core.split("."))
    return parts, prerelease

def compare_semver(v1: str, v2: str) -> int:
    """Returns 1 if v1 > v2, -1 if v1 < v2, 0 if v1 == v2 according to SemVer 2.0."""
    p1, pre1 = parse_semver(v1)
    p2, pre2 = parse_semver(v2)
    if p1 != p2:
        return 1 if p1 > p2 else -1
    # BUG: When core version matches, ignores pre-release and considers them equal
    return 0
''',
        "fixed_code": '''def parse_semver(v_str: str):
    prerelease = None
    if "-" in v_str:
        core, prerelease = v_str.split("-", 1)
    else:
        core = v_str
    parts = tuple(int(x) for x in core.split("."))
    return parts, prerelease

def compare_semver(v1: str, v2: str) -> int:
    """Returns 1 if v1 > v2, -1 if v1 < v2, 0 if v1 == v2 according to SemVer 2.0."""
    p1, pre1 = parse_semver(v1)
    p2, pre2 = parse_semver(v2)
    if p1 != p2:
        return 1 if p1 > p2 else -1
    # Normal version has higher precedence than pre-release version
    if pre1 is None and pre2 is not None:
        return 1
    if pre1 is not None and pre2 is None:
        return -1
    if pre1 == pre2:
        return 0
    return 1 if pre1 > pre2 else -1
''',
        "test_code": '''import pytest
from solution import compare_semver

def test_distinct_major_versions():
    assert compare_semver("2.0.0", "1.0.0") == 1
    assert compare_semver("1.0.0", "2.0.0") == -1

def test_identical_versions():
    assert compare_semver("1.2.3", "1.2.3") == 0
''',
        "hidden_test_code": '''import pytest
from solution import compare_semver

def test_normal_versus_prerelease():
    # 1.0.0 is greater than 1.0.0-alpha
    assert compare_semver("1.0.0", "1.0.0-alpha") == 1
    assert compare_semver("1.0.0-alpha", "1.0.0") == -1

def test_prerelease_ordering():
    assert compare_semver("1.0.0-beta", "1.0.0-alpha") == 1
    assert compare_semver("1.0.0-alpha.1", "1.0.0-alpha.2") == -1
''',
        "oracle_test_code": '''import pytest
from solution import compare_semver

def test_oracle_semver_lifecycle():
    versions = ["1.0.0-alpha", "1.0.0-beta", "1.0.0-rc", "1.0.0"]
    for i in range(len(versions) - 1):
        assert compare_semver(versions[i], versions[i+1]) == -1
        assert compare_semver(versions[i+1], versions[i]) == 1
''',
        "behavioral_spec": "SemVer precedence requires normal releases to strictly outrank pre-releases with identical core tuples."
    },
    {
        "id": "task_056_date_recurrence_leap_year",
        "category": "boundary_violation",
        "difficulty": "medium",
        "desc": "Handle leap-year Feb 29 rollover in annual schedule recurrence engine",
        "expected": "When start date is Feb 29, subsequent non-leap years clamp to Feb 28",
        "tags": ["datetime", "leap-year", "calendar"],
        "repo": "https://github.com/aegis-benchmark/sched-core",
        "commit": "f601020304050607080910111213141516171819",
        "buggy_code": '''from datetime import date

def next_annual_occurrence(start_date: date, years_ahead: int) -> date:
    """Calculates the date exactly years_ahead in the future.
    For Feb 29 on non-leap target years, defaults to Feb 28.
    """
    if years_ahead < 1:
        raise ValueError("years_ahead must be >= 1")
    target_year = start_date.year + years_ahead
    # BUG: Directly calls date(target_year, month, day) which raises ValueError on Feb 29 in non-leap year
    return date(target_year, start_date.month, start_date.day)
''',
        "fixed_code": '''from datetime import date
import calendar

def next_annual_occurrence(start_date: date, years_ahead: int) -> date:
    """Calculates the date exactly years_ahead in the future.
    For Feb 29 on non-leap target years, defaults to Feb 28.
    """
    if years_ahead < 1:
        raise ValueError("years_ahead must be >= 1")
    target_year = start_date.year + years_ahead
    month = start_date.month
    day = start_date.day
    if month == 2 and day == 29 and not calendar.isleap(target_year):
        day = 28
    return date(target_year, month, day)
''',
        "test_code": '''from datetime import date
import pytest
from solution import next_annual_occurrence

def test_standard_date_recurrence():
    d = date(2020, 5, 15)
    assert next_annual_occurrence(d, 1) == date(2021, 5, 15)
    assert next_annual_occurrence(d, 3) == date(2023, 5, 15)
''',
        "hidden_test_code": '''from datetime import date
import pytest
from solution import next_annual_occurrence

def test_leap_year_feb29_to_non_leap():
    leap_date = date(2024, 2, 29)
    # 2025 is not a leap year -> must return 2025-02-28
    assert next_annual_occurrence(leap_date, 1) == date(2025, 2, 28)
    assert next_annual_occurrence(leap_date, 2) == date(2026, 2, 28)

def test_leap_year_feb29_to_leap():
    leap_date = date(2024, 2, 29)
    # 2028 is a leap year -> must return 2028-02-29
    assert next_annual_occurrence(leap_date, 4) == date(2028, 2, 29)
''',
        "oracle_test_code": '''from datetime import date
import pytest
from solution import next_annual_occurrence

def test_oracle_four_year_cycle():
    d = date(2000, 2, 29)
    res = [next_annual_occurrence(d, i) for i in range(1, 5)]
    assert res == [
        date(2001, 2, 28),
        date(2002, 2, 28),
        date(2003, 2, 28),
        date(2004, 2, 29)
    ]
''',
        "behavioral_spec": "Calendar recurrence must gracefully fall back to Feb 28 on non-leap years without raising ValueError."
    }
]
