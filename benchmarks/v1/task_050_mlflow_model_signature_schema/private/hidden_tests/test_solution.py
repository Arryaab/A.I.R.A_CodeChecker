from solution import validate_tensor_shape

def test_mismatched_feature_dimension_rejected():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 128, 512), expected) is False
    assert validate_tensor_shape((16, 128), expected) is False
