from solution import compute_sliding_window_shape

def test_sliding_window_with_step():
    assert compute_sliding_window_shape(10, 2, 2) == (5, 2)
    assert compute_sliding_window_shape(5, 5, 1) == (1, 5)
    assert compute_sliding_window_shape(3, 5, 1) == (0, 0)
