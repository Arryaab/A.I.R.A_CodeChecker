from datetime import date
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
