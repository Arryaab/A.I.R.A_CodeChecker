def compute_sliding_window_shape(n_elements: int, window_size: int, step: int = 1) -> tuple[int, int]:
    if window_size > n_elements or window_size <= 0:
        return (0, 0)
    # BUG: off-by-one omission of +1 in window count
    num_windows = (n_elements - window_size) // step
    return (num_windows, window_size)
