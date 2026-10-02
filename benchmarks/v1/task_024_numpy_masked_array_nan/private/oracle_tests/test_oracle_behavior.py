import pytest
import math
from solution import nanmean_masked

def test_oracle_happy_path_excludes_both_mask_and_nan():
    data = [1.0, float('nan'), 3.0, 5.0]
    mask = [False, False, False, True]
    # valid values: 1.0 and 3.0 (nan is skipped, 5.0 is masked)
    assert nanmean_masked(data, mask) == 2.0

def test_oracle_boundary_no_masked_no_nan():
    assert nanmean_masked([2.0, 4.0, 6.0], [False, False, False]) == 4.0

def test_oracle_boundary_all_invalid_returns_nan():
    res = nanmean_masked([float('nan'), 1.0], [False, True])
    assert math.isnan(res)

def test_oracle_adversarial_multiple_nans():
    data = [float('nan'), float('nan'), 50.0]
    mask = [False, False, False]
    assert nanmean_masked(data, mask) == 50.0
