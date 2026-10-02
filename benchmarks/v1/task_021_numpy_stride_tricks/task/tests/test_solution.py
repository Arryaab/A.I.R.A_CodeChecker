from solution import compute_sliding_window_shape

def test_sliding_window_shape_standard():
    assert compute_sliding_window_shape(10, 3, 1) == (8, 3)
