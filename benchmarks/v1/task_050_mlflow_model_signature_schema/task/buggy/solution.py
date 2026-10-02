def validate_tensor_shape(actual_shape: tuple[int, ...], expected_shape: tuple[int, ...]) -> bool:
    if len(actual_shape) != len(expected_shape):
        return False
    for a, e in zip(actual_shape, expected_shape):
        # BUG: does not treat -1 as dynamic wildcard dimension
        if a != e:
            return False
    return True
