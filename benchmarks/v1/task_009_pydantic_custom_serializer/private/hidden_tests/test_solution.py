from datetime import datetime
from solution import custom_serializer

def test_datetime_serialized_iso():
    dt = datetime(2026, 9, 27, 12, 0, 0)
    assert custom_serializer(dt) == "2026-09-27T12:00:00"
