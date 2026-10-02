from datetime import date
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
