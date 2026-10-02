from solution import validate_tensor_shape

def test_dynamic_batch_size_allowed():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 128, 768), expected) is True
    assert validate_tensor_shape((1, 128, 768), expected) is True
