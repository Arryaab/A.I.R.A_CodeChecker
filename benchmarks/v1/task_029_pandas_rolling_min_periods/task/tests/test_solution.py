from solution import rolling_mean

def test_min_periods_with_nulls():
    s = [10.0, None, None, 20.0]
    res = rolling_mean(s, window=3, min_periods=2)
    assert res[2] is None  # only 1 valid element in window [10, None, None]
