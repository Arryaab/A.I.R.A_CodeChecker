import pytest
from datetime import datetime
from solution import convert_tz_utc

def test_oracle_happy_path_day_rollover():
    dt = datetime(2026, 9, 27, 23, 0)
    res = convert_tz_utc(dt, 2)
    assert res == datetime(2026, 9, 28, 1, 0)

def test_oracle_happy_path_negative_offset():
    dt = datetime(2026, 9, 28, 1, 0)
    res = convert_tz_utc(dt, -2)
    assert res == datetime(2026, 9, 27, 23, 0)

def test_oracle_boundary_zero_offset():
    dt = datetime(2026, 5, 1, 12, 0)
    assert convert_tz_utc(dt, 0) == dt
