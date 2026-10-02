from solution import broadcast_shapes

def test_broadcast_singleton_in_second_shape():
    s1 = (4, 3)
    s2 = (4, 1)
    assert broadcast_shapes(s1, s2) == (4, 3)
