from solution import align_multiindex_data

def test_multiindex_overlapping_keys():
    d1 = {("A", 1): 5, ("A", 2): 10}
    d2 = {("A", 1): 3, ("B", 1): 7}
    res = align_multiindex_data(d1, d2)
    assert res[("A", 1)] == 8
    assert res[("B", 1)] == 7
