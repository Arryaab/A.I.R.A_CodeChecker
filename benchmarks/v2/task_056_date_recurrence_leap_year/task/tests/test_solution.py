from datetime import date
import pytest
from solution import next_annual_occurrence

def test_standard_date_recurrence():
    d = date(2020, 5, 15)
    assert next_annual_occurrence(d, 1) == date(2021, 5, 15)
    assert next_annual_occurrence(d, 3) == date(2023, 5, 15)
