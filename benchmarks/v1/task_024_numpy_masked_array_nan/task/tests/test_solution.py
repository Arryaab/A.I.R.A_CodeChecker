import math
from solution import nanmean_masked

def test_nan_filtered_from_unmasked():
    data = [1.0, float('nan'), 3.0]
    mask = [False, False, False]
    assert nanmean_masked(data, mask) == 2.0
