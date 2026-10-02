from datetime import datetime
from solution import convert_tz_utc

def test_negative_day_boundary_wrap():
    dt = datetime(2026, 9, 27, 1, 0)
    res = convert_tz_utc(dt, -3)
    assert res == datetime(2026, 9, 26, 22, 0)
