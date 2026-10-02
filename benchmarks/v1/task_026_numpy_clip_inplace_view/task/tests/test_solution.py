from solution import clip_array

def test_clip_out_of_bounds():
    data = [-5.0, 0.0, 5.0, 15.0]
    res = clip_array(data, 0.0, 10.0)
    assert res == [0.0, 0.0, 5.0, 10.0]
