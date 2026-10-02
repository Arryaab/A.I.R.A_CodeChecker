from solution import dequantize_weights

def test_dequantize_scale_multiplication():
    q = [10, -5, 0]
    res = dequantize_weights(q, 0.02)
    assert abs(res[0] - 0.2) < 1e-5
    assert abs(res[1] - (-0.1)) < 1e-5
