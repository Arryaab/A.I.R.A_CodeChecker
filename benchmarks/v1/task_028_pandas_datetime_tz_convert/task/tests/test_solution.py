from datetime import datetime
from solution import convert_tz_utc

def test_day_boundary_wrap():
    dt = datetime(2026, 9, 27, 23, 0)
    res = convert_tz_utc(dt, 2)
    assert res == datetime(2026, 9, 28, 1, 0)
