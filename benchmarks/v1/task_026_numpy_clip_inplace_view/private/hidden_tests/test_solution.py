from solution import clip_array

def test_clip_all_within_bounds():
    data = [2.0, 4.0, 6.0]
    assert clip_array(data, 0.0, 10.0) == [2.0, 4.0, 6.0]
