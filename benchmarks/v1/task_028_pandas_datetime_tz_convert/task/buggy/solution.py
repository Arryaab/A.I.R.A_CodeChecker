from datetime import datetime, timedelta

def convert_tz_utc(dt: datetime, offset_hours: int) -> datetime:
    # BUG: uses datetime replace on hour instead of timedelta addition
    new_hour = (dt.hour + offset_hours) % 24
    return dt.replace(hour=new_hour)
