from solution import dequantize_weights

def test_dequantize_zeros():
    assert dequantize_weights([0, 0], 0.5) == [0.0, 0.0]
