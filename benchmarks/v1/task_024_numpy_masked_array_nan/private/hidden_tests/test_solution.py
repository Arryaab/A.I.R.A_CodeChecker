import math
from solution import nanmean_masked

def test_all_masked_or_nan_returns_nan():
    data = [float('nan'), 5.0]
    mask = [False, True]
    assert math.isnan(nanmean_masked(data, mask))
