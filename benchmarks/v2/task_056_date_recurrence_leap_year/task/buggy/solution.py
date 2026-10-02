from datetime import date

def next_annual_occurrence(start_date: date, years_ahead: int) -> date:
    """Calculates the date exactly years_ahead in the future.
    For Feb 29 on non-leap target years, defaults to Feb 28.
    """
    if years_ahead < 1:
        raise ValueError("years_ahead must be >= 1")
    target_year = start_date.year + years_ahead
    # BUG: Directly calls date(target_year, month, day) which raises ValueError on Feb 29 in non-leap year
    return date(target_year, start_date.month, start_date.day)
