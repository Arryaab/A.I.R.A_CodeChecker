from solution import rolling_mean

def test_rolling_mean_standard():
    s = [1.0, 2.0, 3.0, 4.0]
    res = rolling_mean(s, window=2, min_periods=2)
    assert res == [None, 1.5, 2.5, 3.5]
