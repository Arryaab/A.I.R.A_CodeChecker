from solution import range_sum

def test_range_sum_pass():
    assert range_sum(1, 0) == 0

def test_range_sum_fail():
    assert range_sum(1, 3) == 6
